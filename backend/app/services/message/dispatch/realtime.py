"""Realtime dispatch helpers for non-timeline message events."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import MessageTransportProvider, MessageType
from app.models.message import MessageEndpoint
from app.services.message.providers.leancloud import service as leancloud_service
from app.services.message.websocket.manager import ws_manager
from app.type_defs import JSONDict
from app.utils.logging import get_logger
from app.utils.snowflake import generate_snowflake_id

logger = get_logger(__name__)


def _now_utc() -> datetime:
    return datetime.now(UTC)


async def _fanout_websocket_typing(
    *,
    endpoint_ids: list[int],
    conversation_id: str,
    from_qiao_id: str,
    to_qiao_id: str,
    typing_state: str,
    time_ms: int,
) -> None:
    payload = {
        "event_type": "typing",
        "typing": {
            "conversation_id": conversation_id,
            "from_qiao_id": from_qiao_id,
            "to_qiao_id": to_qiao_id,
            "typing_state": typing_state,
            "time_ms": time_ms,
        },
    }
    frame = {
        "type": "event",
        "ws_frame_id": f"evt_typing_{conversation_id}_{time_ms}",
        "payload": payload,
    }

    for endpoint_id in endpoint_ids:
        ok = await ws_manager.send_json(endpoint_id, frame)
        if not ok:
            await ws_manager.unregister(endpoint_id)


async def _fanout_leancloud_typing(
    db: AsyncSession,
    *,
    target_client_ids: list[str],
    conversation_id: str,
    from_qiao_id: str,
    to_qiao_id: str,
    typing_state: str,
    time_ms: int,
) -> None:
    message_type = MessageType.TYPING_START if typing_state == "start" else MessageType.TYPING_END
    msg_id = f"typing_{generate_snowflake_id()}"
    extra_fields: JSONDict = {"sent_time": time_ms}

    for target_client_id in target_client_ids:
        result = await leancloud_service.send_message_to_client(
            db,
            target_client_id=target_client_id,
            from_qiao_id=from_qiao_id,
            to_qiao_id=to_qiao_id,
            conv_id=conversation_id,
            content="",
            message_type=int(message_type),
            action=None,
            extra_fields=extra_fields,
            msg_id=msg_id,
            supports_typing=True,
            transient=True,
        )
        if not result.success:
            logger.warning(
                "typing_fanout_leancloud_send_failed",
                conversation_id=conversation_id,
                target_client_id=target_client_id,
                error_code=result.error_code,
                error_message=result.error_message,
            )


async def fanout_typing_event(
    db: AsyncSession,
    *,
    owner_user_id: int,
    conversation_id: str,
    from_qiao_id: str,
    to_qiao_id: str,
    typing_state: str,
    time_ms: int,
) -> None:
    """Best-effort realtime fanout for typing events."""
    if typing_state not in {"start", "end"}:
        raise ValueError(f"Unsupported typing_state: {typing_state}")

    try:
        now = _now_utc()
        endpoints = list(
            (
                await db.execute(
                    select(MessageEndpoint).where(
                        and_(
                            MessageEndpoint.user_id == owner_user_id,
                            or_(
                                MessageEndpoint.lease_expires_at.is_(None),
                                MessageEndpoint.lease_expires_at > now,
                            ),
                        )
                    )
                )
            )
            .scalars()
            .all()
        )

        websocket_endpoint_ids: list[int] = []
        leancloud_target_client_ids: list[str] = []
        for endpoint in endpoints:
            provider = int(endpoint.provider)
            if provider == int(MessageTransportProvider.WEBSOCKET):
                websocket_endpoint_ids.append(int(endpoint.id))
                continue
            if provider == int(MessageTransportProvider.LEANCLOUD):
                if endpoint.target_key:
                    leancloud_target_client_ids.append(endpoint.target_key)
                continue

            logger.info(
                "typing_unsupported_provider",
                owner_user_id=owner_user_id,
                conversation_id=conversation_id,
                endpoint_id=int(endpoint.id),
                provider=provider,
            )

        if websocket_endpoint_ids:
            await _fanout_websocket_typing(
                endpoint_ids=websocket_endpoint_ids,
                conversation_id=conversation_id,
                from_qiao_id=from_qiao_id,
                to_qiao_id=to_qiao_id,
                typing_state=typing_state,
                time_ms=time_ms,
            )
        if leancloud_target_client_ids:
            await _fanout_leancloud_typing(
                db,
                target_client_ids=leancloud_target_client_ids,
                conversation_id=conversation_id,
                from_qiao_id=from_qiao_id,
                to_qiao_id=to_qiao_id,
                typing_state=typing_state,
                time_ms=time_ms,
            )
    except Exception:
        logger.exception(
            "typing_fanout_failed",
            owner_user_id=owner_user_id,
            conversation_id=conversation_id,
            from_qiao_id=from_qiao_id,
            to_qiao_id=to_qiao_id,
            typing_state=typing_state,
            time_ms=time_ms,
        )
