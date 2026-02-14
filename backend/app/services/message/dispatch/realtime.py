"""Realtime dispatch helpers for non-timeline message events."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import MessageTransportProvider
from app.models.message import MessageEndpoint
from app.services.message.websocket.manager import ws_manager
from app.utils.logging import get_logger

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
        for endpoint in endpoints:
            provider = int(endpoint.provider)
            if provider == int(MessageTransportProvider.WEBSOCKET):
                websocket_endpoint_ids.append(int(endpoint.id))
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
