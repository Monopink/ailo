"""Base message provider interfaces and shared data structures."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

from app.services.message.schemas import InboundMessageEvent

if TYPE_CHECKING:
    from app.models.message import MessageEndpoint, MessageHistory


@dataclass
class MessageResult:
    """Standardized message operation result."""

    success: bool
    msg_id_provider: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class MessageProvider(Protocol):
    """Lifecycle-capable provider contract (initialize/send/check health)."""

    async def initialize_service(self) -> bool: ...

    async def initialize_user(self, qiao_id: str) -> bool: ...

    async def deinitialize_user(self, qiao_id: str) -> bool: ...

    async def send_message(
        self,
        from_qiao_id: str,
        to_qiao_id: str,
        conv_id: str,
        content: str,
        message_type: int = 1,
        extra_fields: dict[str, Any] | None = None,
        msg_id: str | None = None,
    ) -> MessageResult: ...

    async def send_message_as_system(
        self,
        to_qiao_id: str,
        conv_id: str,
        content: str,
        message_type: int = 4,
        action: dict[str, Any] | None = None,
        extra_fields: dict[str, Any] | None = None,
        msg_id: str | None = None,
    ) -> MessageResult: ...

    async def broadcast_message(
        self,
        conversation_id: str,
        from_qiao_id: str,
        to_qiao_ids: list[str],
        content: str,
        message_type: int = 1,
    ) -> MessageResult: ...

    async def fetch_messages_by_time_range(
        self,
        conversation_id: str,
        start_time: int,
        end_time: int,
        limit: int = 1000,
        include_start: bool = False,
    ) -> list[InboundMessageEvent]: ...

    async def check_users_online(self, qiao_ids: list[str]) -> dict[str, bool]: ...

    async def check_health(self) -> tuple[bool, str | None]: ...


class TimelineEndpointSender(Protocol):
    """Endpoint-level sender contract for timeline dispatch."""

    async def send_to_endpoint(
        self,
        *,
        endpoint: MessageEndpoint,
        message: MessageHistory,
    ) -> MessageResult: ...


async def send_message_via_provider(
    provider: MessageProvider,
    conversation_id: str,
    from_qiao_id: str,
    to_qiao_id: str,
    content: str,
    message_type: int = 1,
    extra_fields: dict[str, Any] | None = None,
    msg_id: str | None = None,
) -> MessageResult:
    """Send single message using a specific provider."""
    return await provider.send_message(
        from_qiao_id=from_qiao_id,
        to_qiao_id=to_qiao_id,
        conv_id=conversation_id,
        content=content,
        message_type=message_type,
        extra_fields=extra_fields,
        msg_id=msg_id,
    )


async def broadcast_message_via_provider(
    provider: MessageProvider,
    conversation_id: str,
    from_qiao_id: str,
    to_qiao_ids: list[str],
    content: str,
    message_type: int = 1,
) -> MessageResult:
    """Broadcast message using a specific provider."""
    return await provider.broadcast_message(
        conversation_id=conversation_id,
        from_qiao_id=from_qiao_id,
        to_qiao_ids=to_qiao_ids,
        content=content,
        message_type=message_type,
    )


async def fetch_messages_via_provider(
    provider: MessageProvider,
    conversation_id: str,
    start_time: int,
    end_time: int,
    limit: int = 1000,
) -> list[InboundMessageEvent]:
    """Fetch messages using a specific provider."""
    return await provider.fetch_messages_by_time_range(
        conversation_id=conversation_id,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
    )
