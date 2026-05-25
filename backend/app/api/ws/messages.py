"""WebSocket messages endpoint.

This is a provider-like transport channel for realtime messaging (transport only).
Business logic lives in the unified message pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.database import get_sessionmaker
from app.crud.contact import contact as contact_crud
from app.crud.user import user as user_crud
from app.enums import DetectionSource
from app.exceptions.error_codes import build_error_code
from app.models.message import MessageDevice, MessageEndpoint, MessageHistory
from app.models.user import User
from app.services.message.inbound.router import route_message
from app.services.message.presence import upsert_websocket_presence_endpoint
from app.services.message.providers.websocket import (
    WebSocketPayloadValidationError,
    build_send_message_event,
    build_typing_event,
    parse_send_message_payload,
    parse_typing_payload,
)
from app.services.message.websocket.manager import ws_manager
from app.services.message.websocket.session_ticket import verify_ws_session_ticket
from app.services.security import (
    AttackScanField,
    InvalidClientIPError,
    SecurityRequestContext,
    enforce_attack_scan,
    is_ip_blocked,
)
from app.utils.client_ip import ClientIPResolutionError, get_client_ip
from app.utils.logging import get_logger

WS_PRESENCE_LEASE_TTL_SECONDS = 90

logger = get_logger(__name__)

router = APIRouter()


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _now_ms() -> int:
    return int(_now_utc().timestamp() * 1000)


async def _send_ack(ws: WebSocket, *, ws_frame_id: str, payload: dict[str, object]) -> None:
    await ws.send_json({"type": "ack", "ws_frame_id": ws_frame_id, "payload": payload})


def _new_request_id() -> str:
    return f"req_{uuid4().hex[:12]}"


def _build_ws_error_payload(*, status_code: int, detail: str) -> dict[str, object]:
    error_code = build_error_code(path="/ws/messages", status_code=status_code, detail=detail)
    message = (
        f"系统错误（{error_code}）"
        if status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR
        else detail
    )
    return {
        "error_code": error_code,
        "message": message,
        "request_id": _new_request_id(),
    }


async def _send_error(ws: WebSocket, *, ws_frame_id: str, status_code: int, detail: str) -> None:
    await ws.send_json(
        {
            "type": "error",
            "ws_frame_id": ws_frame_id,
            "payload": _build_ws_error_payload(status_code=status_code, detail=detail),
        }
    )


async def _authenticate_ws_ticket(db: AsyncSession, *, ws_ticket: str) -> tuple[User, UUID] | None:
    claims = verify_ws_session_ticket(ws_ticket)
    if claims is None:
        return None

    user = await user_crud.get_by_qiao_id(db, qiao_id=claims.user_qiao_id)
    if not user:
        return None
    if int(user.id) != claims.user_id:
        return None
    if not await user_crud.is_active(user):
        return None
    return user, claims.device_id


async def _close_ws_with_error(
    ws: WebSocket,
    *,
    ws_frame_id: str,
    status_code: int,
    detail: str,
    close_code: int,
) -> None:
    await _send_error(ws, ws_frame_id=ws_frame_id, status_code=status_code, detail=detail)
    await ws.close(code=close_code)


def _parse_inbound_frame(data: object) -> tuple[str, str, dict[str, object]] | None:
    if not isinstance(data, dict):
        return None

    msg_type = data.get("type")
    if not isinstance(msg_type, str) or not msg_type:
        return None

    ws_frame_id_raw = data.get("ws_frame_id")
    ws_frame_id = ws_frame_id_raw if isinstance(ws_frame_id_raw, str) and ws_frame_id_raw else "*"

    payload_raw = data.get("payload")
    payload: dict[str, object] = payload_raw if isinstance(payload_raw, dict) else {}

    return msg_type, ws_frame_id, payload


@dataclass(slots=True)
class _WSContext:
    user_id: int
    user_qiao_id: str
    device_uuid: UUID
    endpoint_id: int


async def _get_or_create_device(
    db: AsyncSession, *, user_id: int, user_qiao_id: str, device_id: UUID
) -> MessageDevice:
    result = await db.execute(
        select(MessageDevice).where(
            MessageDevice.user_id == user_id,
            MessageDevice.device_id == device_id,
        )
    )
    device = result.scalar_one_or_none()
    if device:
        return device

    now = _now_utc()
    device = MessageDevice(
        user_id=user_id,
        user_qiao_id=user_qiao_id,
        device_id=device_id,
        last_acked_msg_id=None,
        last_acked_msg_sent_at=now,  # No history backfill.
        last_pull_at=now,
        last_seen_at=now,
    )
    db.add(device)
    await db.flush()
    return device


async def _upsert_presence_endpoint(
    db: AsyncSession,
    *,
    user_id: int,
    user_qiao_id: str,
    device_id: UUID,
    lease_ttl_seconds: int,
) -> MessageEndpoint:
    settings = get_settings()
    return await upsert_websocket_presence_endpoint(
        db,
        user_id=user_id,
        user_qiao_id=user_qiao_id,
        device_id=device_id,
        lease_ttl_seconds=lease_ttl_seconds,
        owner_instance_id=settings.message_instance_id,
        owner_lease_ttl_seconds=settings.MESSAGE_OWNER_LEASE_TTL_SECONDS,
    )


async def _handle_auth(  # noqa: PLR0911
    ws: WebSocket,
    *,
    session_factory: async_sessionmaker[AsyncSession],
    ws_frame_id: str,
    payload: dict[str, object],
) -> _WSContext | None:
    ws_ticket = payload.get("ws_ticket")
    device_id = payload.get("device_id")

    if not isinstance(ws_ticket, str) or not ws_ticket:
        logger.warning("ws_auth_rejected_missing_ticket", ws_frame_id=ws_frame_id)
        await _close_ws_with_error(
            ws,
            ws_frame_id=ws_frame_id,
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录失效",
            close_code=1008,
        )
        return None

    if not isinstance(device_id, str) or not device_id:
        logger.warning("ws_auth_rejected_missing_device_id", ws_frame_id=ws_frame_id)
        await _close_ws_with_error(
            ws,
            ws_frame_id=ws_frame_id,
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="device_id 缺失",
            close_code=1008,
        )
        return None

    try:
        device_uuid = UUID(device_id)
    except ValueError:
        logger.warning(
            "ws_auth_rejected_invalid_device_id",
            ws_frame_id=ws_frame_id,
            device_id=device_id,
        )
        await _close_ws_with_error(
            ws,
            ws_frame_id=ws_frame_id,
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="device_id 无效",
            close_code=1008,
        )
        return None

    async with session_factory() as db:
        try:
            client_ip = get_client_ip(ws)
        except ClientIPResolutionError as exc:
            logger.warning(
                "ws_auth_rejected_invalid_client_ip",
                ws_frame_id=ws_frame_id,
                reason=exc.reason,
                detail=str(exc),
            )
            await _close_ws_with_error(
                ws,
                ws_frame_id=ws_frame_id,
                status_code=status.HTTP_403_FORBIDDEN,
                detail="请求来源受限",
                close_code=1008,
            )
            return None

        try:
            is_blocked = await is_ip_blocked(db, client_ip)
        except InvalidClientIPError:
            logger.warning(
                "ws_auth_rejected_invalid_client_ip_after_normalization",
                ws_frame_id=ws_frame_id,
                client_ip=client_ip,
            )
            await _close_ws_with_error(
                ws,
                ws_frame_id=ws_frame_id,
                status_code=status.HTTP_403_FORBIDDEN,
                detail="请求来源受限",
                close_code=1008,
            )
            return None

        if is_blocked:
            logger.warning(
                "ws_auth_rejected_ip_blocked",
                ws_frame_id=ws_frame_id,
                client_ip=client_ip,
            )
            await _close_ws_with_error(
                ws,
                ws_frame_id=ws_frame_id,
                status_code=status.HTTP_403_FORBIDDEN,
                detail="请求来源受限",
                close_code=1008,
            )
            return None

        auth_result = await _authenticate_ws_ticket(db, ws_ticket=ws_ticket)
        if auth_result is None:
            logger.warning(
                "ws_auth_rejected_ticket_invalid",
                ws_frame_id=ws_frame_id,
                client_ip=client_ip,
            )
            await _close_ws_with_error(
                ws,
                ws_frame_id=ws_frame_id,
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="登录失效",
                close_code=1008,
            )
            return None
        user, ticket_device_id = auth_result
        if ticket_device_id != device_uuid:
            logger.warning(
                "ws_auth_rejected_device_mismatch",
                ws_frame_id=ws_frame_id,
                ticket_device_id=str(ticket_device_id),
                requested_device_id=str(device_uuid),
                user_id=int(user.id),
            )
            await _close_ws_with_error(
                ws,
                ws_frame_id=ws_frame_id,
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="登录失效",
                close_code=1008,
            )
            return None

        user_id = int(user.id)
        user_qiao_id = str(user.qiao_id)

        match = await enforce_attack_scan(
            db,
            context=SecurityRequestContext(
                detection_source=DetectionSource.WS_AUTH,
                request_method="WS_AUTH",
                request_path="/ws/messages",
                client_ip=client_ip,
                request_id=_new_request_id(),
                user_id=user_id,
                user_qiao_id=user_qiao_id,
                user_stats_shadow_only=True,
            ),
            fields=[
                AttackScanField(
                    field_name="ws_ticket",
                    raw_value=ws_ticket,
                    field_type="opaque_token",
                ),
                AttackScanField(
                    field_name="device_id",
                    raw_value=device_id,
                    field_type="identifier",
                ),
                AttackScanField(
                    field_name="user_agent",
                    raw_value=ws.headers.get("user-agent", ""),
                    field_type="free_text",
                ),
            ],
            extra_evidence={"layer": "ws_messages"},
        )
        if match is not None:
            logger.warning(
                "ws_auth_rejected_attack_detected",
                ws_frame_id=ws_frame_id,
                client_ip=client_ip,
                rule_code=match.rule_code,
            )
            await _close_ws_with_error(
                ws,
                ws_frame_id=ws_frame_id,
                status_code=status.HTTP_403_FORBIDDEN,
                detail="请求来源受限",
                close_code=1008,
            )
            return None

        lease_ttl_seconds = WS_PRESENCE_LEASE_TTL_SECONDS

        device = await _get_or_create_device(
            db,
            user_id=user_id,
            user_qiao_id=user_qiao_id,
            device_id=device_uuid,
        )
        endpoint = await _upsert_presence_endpoint(
            db,
            user_id=user_id,
            user_qiao_id=user_qiao_id,
            device_id=device.device_id,
            lease_ttl_seconds=lease_ttl_seconds,
        )
        endpoint_id = int(endpoint.id)

        await db.commit()

    await ws_manager.register(endpoint_id, ws)
    await _send_ack(ws, ws_frame_id=ws_frame_id, payload={"ok": True})
    return _WSContext(
        user_id=user_id,
        user_qiao_id=user_qiao_id,
        device_uuid=device_uuid,
        endpoint_id=endpoint_id,
    )


async def _handle_ping(
    ws: WebSocket,
    *,
    session_factory: async_sessionmaker[AsyncSession],
    ws_frame_id: str,
    ctx: _WSContext,
) -> None:
    async with session_factory() as db:
        lease_ttl_seconds = WS_PRESENCE_LEASE_TTL_SECONDS
        settings = get_settings()

        endpoint = await upsert_websocket_presence_endpoint(
            db,
            user_id=ctx.user_id,
            user_qiao_id=ctx.user_qiao_id,
            device_id=ctx.device_uuid,
            lease_ttl_seconds=lease_ttl_seconds,
            owner_instance_id=settings.message_instance_id,
            owner_lease_ttl_seconds=settings.MESSAGE_OWNER_LEASE_TTL_SECONDS,
        )
        ctx.endpoint_id = int(endpoint.id)
        await db.commit()

    await _send_ack(ws, ws_frame_id=ws_frame_id, payload={"ok": True})


async def _find_duplicate_message(
    db: AsyncSession,
    *,
    conversation_id: str,
    msg_id_client: str,
) -> MessageHistory | None:
    dup_result = await db.execute(
        select(MessageHistory).where(
            MessageHistory.conversation_id == conversation_id,
            MessageHistory.msg_id_client == msg_id_client,
        )
    )
    return dup_result.scalar_one_or_none()


async def _handle_send_message(
    ws: WebSocket,
    *,
    session_factory: async_sessionmaker[AsyncSession],
    ws_frame_id: str,
    payload: dict[str, object],
    ctx: _WSContext,
) -> None:
    try:
        normalized_payload = parse_send_message_payload(payload)
    except WebSocketPayloadValidationError as exc:
        await _send_error(
            ws,
            ws_frame_id=ws_frame_id,
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message,
        )
        return

    async with session_factory() as db:
        dup = await _find_duplicate_message(
            db,
            conversation_id=normalized_payload.conversation_id,
            msg_id_client=normalized_payload.msg_id_client,
        )
        if dup is not None:
            sent_time_ms = int(dup.sent_at.timestamp() * 1000) if dup.sent_at else 0
            await _send_ack(
                ws,
                ws_frame_id=ws_frame_id,
                payload={
                    "ok": True,
                    "msg_id_server": dup.msg_id_server,
                    "sent_time_ms": sent_time_ms,
                },
            )
            return

        contact = await contact_crud.get_by_conversation_id(
            db, conversation_id=normalized_payload.conversation_id
        )
        if not contact or contact.user_id != ctx.user_id or contact.is_deleted != 0:
            await _send_error(
                ws,
                ws_frame_id=ws_frame_id,
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权操作",
            )
            return

        event = build_send_message_event(
            payload=normalized_payload,
            from_qiao_id=ctx.user_qiao_id,
            to_qiao_id=contact.contact_qiao_id,
            sent_at_ms=_now_ms(),
            inbound_device_id=ctx.device_uuid,
        )

        try:
            stored = await route_message(db, event)
        except IntegrityError:
            await db.rollback()
            dup2 = await _find_duplicate_message(
                db,
                conversation_id=normalized_payload.conversation_id,
                msg_id_client=normalized_payload.msg_id_client,
            )
            if dup2 is not None:
                sent_time_ms = int(dup2.sent_at.timestamp() * 1000) if dup2.sent_at else 0
                await _send_ack(
                    ws,
                    ws_frame_id=ws_frame_id,
                    payload={
                        "ok": True,
                        "msg_id_server": dup2.msg_id_server,
                        "sent_time_ms": sent_time_ms,
                    },
                )
                return
            raise

        if stored is None or not stored.msg_id_server:
            await _send_error(
                ws,
                ws_frame_id=ws_frame_id,
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="发送失败",
            )
            return

        # Durability: ACK only after the idempotency record is committed.
        await db.commit()

        sent_time_ms = int(stored.sent_at.timestamp() * 1000) if stored.sent_at else 0
        await _send_ack(
            ws,
            ws_frame_id=ws_frame_id,
            payload={
                "ok": True,
                "msg_id_server": stored.msg_id_server,
                "sent_time_ms": sent_time_ms,
            },
        )


async def _handle_typing(
    ws: WebSocket,
    *,
    session_factory: async_sessionmaker[AsyncSession],
    ws_frame_id: str,
    payload: dict[str, object],
    ctx: _WSContext,
) -> None:
    try:
        normalized_payload = parse_typing_payload(payload)
    except WebSocketPayloadValidationError as exc:
        await _send_error(
            ws,
            ws_frame_id=ws_frame_id,
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message,
        )
        return

    async with session_factory() as db:
        contact = await contact_crud.get_by_conversation_id(
            db, conversation_id=normalized_payload.conversation_id
        )
        if not contact or contact.user_id != ctx.user_id or contact.is_deleted != 0:
            await _send_error(
                ws,
                ws_frame_id=ws_frame_id,
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权操作",
            )
            return

        event = build_typing_event(
            payload=normalized_payload,
            from_qiao_id=ctx.user_qiao_id,
            to_qiao_id=contact.contact_qiao_id,
            sent_at_ms=_now_ms(),
            inbound_device_id=ctx.device_uuid,
        )
        await route_message(db, event)
        await db.commit()

    await _send_ack(ws, ws_frame_id=ws_frame_id, payload={"ok": True})


@router.websocket("/ws/messages")
async def ws_messages(ws: WebSocket) -> None:
    """Realtime message channel."""
    await ws.accept()

    session_factory: async_sessionmaker[AsyncSession] = get_sessionmaker()
    ctx: _WSContext | None = None

    try:
        while True:
            parsed = _parse_inbound_frame(await ws.receive_json())
            if parsed is None:
                await _close_ws_with_error(
                    ws,
                    ws_frame_id="*",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="请求格式错误",
                    close_code=1008,
                )
                return

            msg_type, ws_frame_id, payload = parsed

            if msg_type == "auth":
                ctx = await _handle_auth(
                    ws,
                    session_factory=session_factory,
                    ws_frame_id=ws_frame_id,
                    payload=payload,
                )
                if ctx is None:
                    return
                continue

            if ctx is None:
                await _close_ws_with_error(
                    ws,
                    ws_frame_id=ws_frame_id,
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="需要先登录",
                    close_code=1008,
                )
                return

            if msg_type == "ping":
                await _handle_ping(
                    ws,
                    session_factory=session_factory,
                    ws_frame_id=ws_frame_id,
                    ctx=ctx,
                )
                continue

            if msg_type == "send_message":
                await _handle_send_message(
                    ws,
                    session_factory=session_factory,
                    ws_frame_id=ws_frame_id,
                    payload=payload,
                    ctx=ctx,
                )
                continue

            if msg_type == "typing":
                await _handle_typing(
                    ws,
                    session_factory=session_factory,
                    ws_frame_id=ws_frame_id,
                    payload=payload,
                    ctx=ctx,
                )
                continue

            await _send_error(
                ws,
                ws_frame_id=ws_frame_id,
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="未知消息类型",
            )

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.error(
            "ws_messages_loop_failed",
            error=str(exc),
            endpoint_id=ctx.endpoint_id if ctx is not None else None,
            user_id=ctx.user_id if ctx is not None else None,
            exc_info=True,
        )
    finally:
        if ctx is not None:
            await ws_manager.unregister(ctx.endpoint_id)
