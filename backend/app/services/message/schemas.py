"""
Message event schemas shared across the messaging pipeline.

These Pydantic models mirror docs/spec/message/schema.md and provide
a single source of truth for inbound/outbound message payloads.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.enums import MessageTransportProvider, MessageType

CURRENT_SCHEMA_VERSION = "1.0.0"
EventType = Literal["inbound_message", "outbound_message"]


class EventMetadata(BaseModel):
    """Whitelisted business metadata for message events."""

    model_config = ConfigDict(extra="forbid")

    action: dict[str, Any] | None = Field(
        default=None,
        description="Client action payload (e.g., navigate targets for notifications)",
    )
    notification_type: int | None = Field(
        default=None,
        description="Notification type enum value",
    )
    rate_limit_bucket: str | None = Field(
        default=None,
        description="Indicates which rate-limit window (e.g., 10s/60s) applied",
    )
    encryption: str | None = Field(
        default=None,
        description="Transport encryption algorithm identifier",
    )
    encryption_version: str | None = Field(
        default=None,
        description="Encryption schema version",
    )


class BaseMessageEvent(BaseModel):
    """Common fields shared by inbound and outbound message events."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: str = Field(default=CURRENT_SCHEMA_VERSION)
    event_type: EventType
    message_type: MessageType
    conversation_id: str
    from_qiao_id: str
    to_qiao_id: str
    content: str = Field(default="", description="Textual content, optional for control frames")
    sent_at_ms: int = Field(..., description="Event timestamp in milliseconds")
    client_sent_time_ms: int | None = Field(
        default=None,
        description="Client-provided sent time in milliseconds (optional)",
    )
    msg_id_server: str | None = Field(
        default=None,
        description="Server-assigned Snowflake ID; set before persistence",
    )
    msg_id_client: str | None = Field(
        default=None,
        description="Client-generated ID (required for inbound user messages)",
    )
    msg_id_provider_inbound: str | None = None
    inbound_provider: MessageTransportProvider | None = Field(
        default=None,
        description="Inbound transport provider enum (inbound only)",
    )
    inbound_device_id: str | None = Field(
        default=None,
        description="Inbound device_id (UUID string, websocket only)",
    )
    llm_request_id: int | None = Field(
        default=None,
        description="ai_request_logs.id (only set for assistant outbound messages)",
    )
    supports_typing: bool = True
    metadata: EventMetadata = Field(default_factory=EventMetadata)


class InboundMessageEvent(BaseMessageEvent):
    """Inbound event from transport layer (LeanCloud webhook or WebSocket)."""

    event_type: Literal["inbound_message"] = Field(default="inbound_message", frozen=True)
    msg_id_client: str = Field(..., description="Client-generated ID for deduplication")
    msg_id_provider_inbound: str | None = Field(
        default=None,
        description="Provider message ID (LeanCloud msgId); null for websocket inbound",
    )
    inbound_provider: MessageTransportProvider = Field(
        ...,
        description="Inbound transport provider enum",
    )


class OutboundMessageEvent(BaseMessageEvent):
    """System/AI → user outbound event."""

    event_type: Literal["outbound_message"] = Field(default="outbound_message", frozen=True)
