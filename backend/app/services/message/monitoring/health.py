"""Message service health check for websocket-only runtime."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import MessageTransportProvider
from app.models.message import MessageEndpoint
from app.services.message.websocket.manager import ws_manager


async def check_message_service_health(db: AsyncSession) -> dict[str, Any]:
    """Return websocket transport health snapshot."""
    now = datetime.now(UTC)
    active_endpoint_count_result = await db.execute(
        select(func.count(MessageEndpoint.id)).where(
            and_(
                MessageEndpoint.provider == MessageTransportProvider.WEBSOCKET,
                or_(
                    MessageEndpoint.lease_expires_at.is_(None),
                    MessageEndpoint.lease_expires_at > now,
                ),
            )
        )
    )
    active_endpoint_count = int(active_endpoint_count_result.scalar_one() or 0)
    live_connection_count = ws_manager.connection_count()

    return {
        "healthy": True,
        "provider": "websocket",
        "error": None,
        "checked_at": int(now.timestamp() * 1000),
        "details": {
            "active_endpoint_count": active_endpoint_count,
            "live_connection_count": live_connection_count,
        },
    }


async def get_message_service_status(db: AsyncSession) -> dict[str, Any]:
    """Alias for admin/status consumers."""
    return await check_message_service_health(db)
