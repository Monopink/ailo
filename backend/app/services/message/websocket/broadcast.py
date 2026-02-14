"""WebSocket transport broadcast helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import MessageEndpointScope, MessageTransportProvider
from app.models.message import MessageEndpoint
from app.services.message.websocket.manager import ws_manager
from app.utils.logging import get_logger

logger = get_logger(__name__)


def _now_utc() -> datetime:
    return datetime.now(UTC)


async def broadcast_typing_event(
    db: AsyncSession,
    *,
    owner_user_id: int,
    conversation_id: str,
    from_qiao_id: str,
    to_qiao_id: str,
    typing_state: str,
    time_ms: int,
) -> None:
    """Broadcast typing state to all active websocket endpoints of the owner user.

    Typing is not persisted and has no delivery record.
    """
    now = _now_utc()

    endpoints = list(
        (
            await db.execute(
                select(MessageEndpoint).where(
                    and_(
                        MessageEndpoint.user_id == owner_user_id,
                        MessageEndpoint.endpoint_scope == MessageEndpointScope.DEVICE,
                        MessageEndpoint.provider == MessageTransportProvider.WEBSOCKET,
                        MessageEndpoint.lease_expires_at > now,
                    )
                )
            )
        )
        .scalars()
        .all()
    )

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

    for endpoint in endpoints:
        ok = await ws_manager.send_json(endpoint.id, frame)
        if not ok:
            await ws_manager.unregister(endpoint.id)
