"""Realtime dispatch helpers for non-timeline message events."""

from __future__ import annotations

from collections.abc import Mapping
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


async def _send_websocket_event_to_endpoints(
    *,
    endpoint_ids: list[int],
    frame: Mapping[str, object],
) -> None:
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
                            MessageEndpoint.provider == MessageTransportProvider.WEBSOCKET,
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

        endpoint_ids = [int(endpoint.id) for endpoint in endpoints]
        if not endpoint_ids:
            return

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
        await _send_websocket_event_to_endpoints(endpoint_ids=endpoint_ids, frame=frame)
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
