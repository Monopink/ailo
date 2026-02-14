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

from app.core.database import get_sessionmaker
from app.crud.contact import contact as contact_crud
from app.crud.user import user as user_crud
from app.crud.user import user_token as token_crud
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
from app.services.system_config import get_config_int
from app.utils.logging import get_logger

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


async def _authenticate_access_token(db: AsyncSession, *, access_token: str) -> User | None:
    user_token = await token_crud.get_by_access_token(db, token=access_token)
    if not user_token:
        return None
    if user_token.status != 1 or user_token.access_revoked_at is not None:
        return None
    if user_token.access_expires_at < _now_utc():
        return None

    user = await user_crud.get_by_qiao_id(db, qiao_id=user_token.user_qiao_id)
    if not user:
        return None
    if not await user_crud.is_active(user):
        return None

    user_token.last_activity_at = _now_utc()
    db.add(user_token)
    await db.flush()
    return user


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
    return await upsert_websocket_presence_endpoint(
        db,
        user_id=user_id,
        user_qiao_id=user_qiao_id,
        device_id=device_id,
        lease_ttl_seconds=lease_ttl_seconds,
    )


async def _handle_auth(
    ws: WebSocket,
    *,
    session_factory: async_sessionmaker[AsyncSession],
    ws_frame_id: str,
    payload: dict[str, object],
) -> _WSContext | None:
    access_token = payload.get("access_token")
    device_id = payload.get("device_id")

    if not isinstance(access_token, str) or not access_token:
        await _close_ws_with_error(
            ws,
            ws_frame_id=ws_frame_id,
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录失效",
            close_code=1008,
        )
        return None

    if not isinstance(device_id, str) or not device_id:
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
        await _close_ws_with_error(
            ws,
            ws_frame_id=ws_frame_id,
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="device_id 无效",
            close_code=1008,
        )
        return None

    async with session_factory() as db:
        user = await _authenticate_access_token(db, access_token=access_token)
        if not user:
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

        try:
            lease_ttl_seconds = await get_config_int(db, key="ws_presence_lease_ttl_seconds")
        except Exception:
            logger.exception("ws_presence_config_error")
            await _close_ws_with_error(
                ws,
                ws_frame_id=ws_frame_id,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="系统配置异常",
                close_code=1011,
            )
            return None

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
        try:
            lease_ttl_seconds = await get_config_int(db, key="ws_presence_lease_ttl_seconds")
        except Exception:
            logger.exception("ws_presence_config_error")
            await _close_ws_with_error(
                ws,
                ws_frame_id=ws_frame_id,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="系统配置异常",
                close_code=1011,
            )
            return

        endpoint = await upsert_websocket_presence_endpoint(
            db,
            user_id=ctx.user_id,
            user_qiao_id=ctx.user_qiao_id,
            device_id=ctx.device_uuid,
            lease_ttl_seconds=lease_ttl_seconds,
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
    finally:
        if ctx is not None:
            await ws_manager.unregister(ctx.endpoint_id)
