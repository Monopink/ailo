"""
LeanCloud message provider implementation.

This module implements the MessageProvider protocol for LeanCloud messaging service.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.message.schemas import InboundMessageEvent

from ..base import MessageProvider, MessageResult
from . import service


class LeanCloudProvider:
    """
    LeanCloud message provider adapter.

    This class adapts the functional service layer to the MessageProvider protocol.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def initialize_service(self) -> bool:
        """Initialize LeanCloud message service."""
        return await service.initialize_service(self.db)

    async def initialize_user(self, qiao_id: str) -> bool:
        """Initialize user for LeanCloud message service."""
        return await service.initialize_user(qiao_id, self.db)

    async def deinitialize_user(self, qiao_id: str) -> bool:
        """Clean up user's LeanCloud message service state."""
        return await service.deinitialize_user(qiao_id, self.db)

    async def send_message(
        self,
        from_qiao_id: str,
        to_qiao_id: str,
        conv_id: str,
        content: str,
        message_type: int = 1,
        extra_fields: dict | None = None,
        msg_id: str | None = None,
    ) -> MessageResult:
        """Send message through LeanCloud."""
        return await service.send_message(
            self.db,
            from_qiao_id=from_qiao_id,
            to_qiao_id=to_qiao_id,
            conv_id=conv_id,
            content=content,
            message_type=message_type,
            extra_fields=extra_fields,
            msg_id=msg_id,
        )

    async def send_message_as_system(
        self,
        to_qiao_id: str,
        conv_id: str,
        content: str,
        message_type: int = 4,
        action: dict | None = None,
        extra_fields: dict | None = None,
        msg_id: str | None = None,
    ) -> MessageResult:
        """Send message as system through LeanCloud."""
        return await service.send_message_as_system(
            self.db,
            to_qiao_id=to_qiao_id,
            conv_id=conv_id,
            content=content,
            message_type=message_type,
            action=action,
            extra_fields=extra_fields,
            msg_id=msg_id,
        )

    async def broadcast_message(
        self,
        conversation_id: str,
        from_qiao_id: str,
        to_qiao_ids: list[str],
        content: str,
        message_type: int = 1,
    ) -> MessageResult:
        """Broadcast message through LeanCloud."""
        return await service.broadcast_message(
            conversation_id, from_qiao_id, to_qiao_ids, content, message_type
        )

    async def fetch_messages_by_time_range(
        self,
        conversation_id: str,
        start_time: int,
        end_time: int,
        limit: int = 1000,
        include_start: bool = False,
    ) -> list[InboundMessageEvent]:
        """Fetch messages by time range from LeanCloud."""
        return await service.fetch_messages_by_time_range(
            conversation_id, start_time, end_time, limit, include_start
        )

    async def check_users_online(self, qiao_ids: list[str]) -> dict[str, bool]:
        """Check users online status in LeanCloud."""
        return await service.check_users_online(qiao_ids)

    async def check_health(self) -> tuple[bool, str | None]:
        """Check LeanCloud service health."""
        return await service.check_health(self.db)


def create_leancloud_provider(db: AsyncSession) -> MessageProvider:
    """
    Create LeanCloud message provider instance.

    Args:
        db: Database session for configuration access

    Returns:
        MessageProvider instance with LeanCloud implementation
    """
    return LeanCloudProvider(db)


__all__ = [
    "LeanCloudProvider",
    "create_leancloud_provider",
]
