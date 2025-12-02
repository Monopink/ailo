"""
Base message provider interface and data structures.

This module defines the Protocol interface for message providers and
standardized data structures for internal use.
"""

from dataclasses import dataclass, field
from typing import Any, Protocol

from services.message.schemas import InboundMessageEvent


@dataclass
class MessageResult:
    """Standardized message operation result."""

    success: bool
    msg_id_provider: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class MessageProvider(Protocol):
    """
    Message provider protocol interface.

    This protocol defines the contract that all message providers must implement.
    Uses Protocol for type safety while maintaining functional programming style.
    """

    async def initialize_service(self) -> bool:
        """
        Initialize message service (create system conversation, etc.).

        Returns:
            True if initialization successful, False otherwise
        """
        ...

    async def initialize_user(self, qiao_id: str) -> bool:
        """
        Initialize user for message service (subscription, setup, etc.).

        Args:
            qiao_id: User's qiao_id

        Returns:
            True if initialization successful, False otherwise
        """
        ...

    async def deinitialize_user(self, qiao_id: str) -> bool:
        """
        Clean up user's message service state.

        Args:
            qiao_id: User's qiao_id

        Returns:
            True if cleanup successful, False otherwise
        """
        ...

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
        """
        Send message.

        Args:
            from_qiao_id: Sender's qiao_id
            to_qiao_id: Receiver's qiao_id
            conv_id: Internal conversation ID (included in message)
            content: Message content
            message_type: Message type (1=TEXT, 2=IMAGE, etc.)
            extra_fields: Additional payload fields (metadata, typing flags, etc.)
            msg_id: Explicit message ID (server snowflake). Providers must embed this value.

        Returns:
            MessageResult with success status and provider message ID
        """
        ...

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
        """
        Send message as system (from='system').

        Provider implementation handles protocol details (from_client, provider conversation ID, etc.).
        Business layer doesn't need to know about these details.

        Args:
            to_qiao_id: Receiver's qiao_id
            conv_id: Internal conversation ID (included in message)
            content: Message text (already mapped by business layer)
            message_type: Message type to transmit (default Chat Info)
            action: Optional action payload for the client
            extra_fields: Additional root-level fields (e.g., notification_type)
            msg_id: Optional explicit message ID (otherwise generated)

        Returns:
            MessageResult with success status and provider message ID
        """
        ...

    async def broadcast_message(
        self,
        conversation_id: str,
        from_qiao_id: str,
        to_qiao_ids: list[str],
        content: str,
        message_type: int = 1,
    ) -> MessageResult:
        """
        Broadcast message to multiple users.

        Args:
            conversation_id: Conversation ID
            from_qiao_id: Sender's qiao_id
            to_qiao_ids: List of recipient qiao_ids
            content: Message content
            message_type: Message type (1=TEXT, 2=IMAGE, etc.)

        Returns:
            MessageResult with success status and provider message ID
        """
        ...

    async def fetch_messages_by_time_range(
        self,
        conversation_id: str,
        start_time: int,
        end_time: int,
        limit: int = 1000,
        include_start: bool = False,
    ) -> list[InboundMessageEvent]:
        """
        Fetch messages by time range (for server restart synchronization).

        Args:
            conversation_id: Conversation ID
            start_time: Start timestamp in milliseconds
            end_time: End timestamp in milliseconds
            limit: Maximum number of messages to fetch
            include_start: Whether to include messages at start_time

        Returns:
            List of InboundMessageEvent objects
        """
        ...

    async def check_users_online(self, qiao_ids: list[str]) -> dict[str, bool]:
        """
        Check online status of users.

        Args:
            qiao_ids: List of user qiao_ids to check

        Returns:
            Dictionary mapping qiao_id to online status
        """
        ...

    async def check_health(self) -> tuple[bool, str | None]:
        """
        Check provider service health.

        This method should verify that the message service provider is accessible
        and functioning correctly. It should perform a lightweight check that
        doesn't impact service performance.

        Returns:
            Tuple of (is_healthy, error_message)
            - is_healthy: True if service is healthy and accessible
            - error_message: Error description if unhealthy, None if healthy

        Example:
            >>> is_healthy, error = await provider.check_health()
            >>> if not is_healthy:
            ...     logger.error("Service unhealthy", error=error)
        """
        ...


# Convenience functions for functional programming style
async def send_message_via_provider(
    provider: MessageProvider,
    conversation_id: str,
    from_qiao_id: str,
    to_qiao_id: str,
    content: str,
    message_type: int = 1,
    extra_fields: dict | None = None,
    msg_id: str | None = None,
) -> MessageResult:
    """Send single message using specified provider."""
    return await provider.send_message(
        conversation_id, from_qiao_id, to_qiao_id, content, message_type, extra_fields, msg_id
    )


async def broadcast_message_via_provider(
    provider: MessageProvider,
    conversation_id: str,
    from_qiao_id: str,
    to_qiao_ids: list[str],
    content: str,
    message_type: int = 1,
) -> MessageResult:
    """Broadcast message using specified provider."""
    return await provider.broadcast_message(
        conversation_id, from_qiao_id, to_qiao_ids, content, message_type
    )


async def fetch_messages_via_provider(
    provider: MessageProvider,
    conversation_id: str,
    start_time: int,
    end_time: int,
    limit: int = 1000,
) -> list[InboundMessageEvent]:
    """Fetch messages using specified provider."""
    return await provider.fetch_messages_by_time_range(conversation_id, start_time, end_time, limit)
