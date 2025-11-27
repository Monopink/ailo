"""
Message event schemas shared across the messaging pipeline.

These Pydantic models mirror docs/development/message-events-schema.md and provide
a single source of truth for inbound/outbound message payloads.
"""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from enums import MessageType
from pydantic import BaseModel, ConfigDict, Field

CURRENT_SCHEMA_VERSION = "1.0.0"
EventType = Literal["inbound_message", "outbound_message"]


class EventMetadata(BaseModel):
    """Whitelisted business metadata for message events."""

    model_config = ConfigDict(extra="forbid")

    action: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Client action payload (e.g., navigate targets for notifications)",
    )
    notification_type: Optional[int] = Field(
        default=None,
        description="Notification type enum value",
    )
    rate_limit_bucket: Optional[str] = Field(
        default=None,
        description="Indicates which rate-limit window (e.g., 10s/60s) applied",
    )
    encryption: Optional[str] = Field(
        default=None,
        description="Transport encryption algorithm identifier",
    )
    encryption_version: Optional[str] = Field(
        default=None,
        description="Encryption schema version",
    )


class ProviderMetadata(BaseModel):
    """
    Third-party transport metadata.

    Extra keys are allowed so we can capture provider-specific values without
    continuously editing the schema.
    """

    model_config = ConfigDict(extra="allow")

    lc_from: Optional[str] = None
    lc_conv_id: Optional[str] = None
    raw_webhook: Optional[str] = Field(
        default=None,
        description="Raw webhook payload for auditing",
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
    msg_id_server: Optional[str] = Field(
        default=None,
        description="Server-assigned Snowflake ID; set before persistence",
    )
    msg_id_client: Optional[str] = Field(
        default=None,
        description="Client-generated ID (required for inbound user messages)",
    )
    msg_id_provider_inbound: Optional[str] = None
    msg_id_provider_outbound: Optional[str] = None
    supports_typing: bool = True
    client_sent_time: Optional[int] = Field(
        default=None,
        description="Original client timestamp (if provided)",
    )
    metadata: EventMetadata = Field(default_factory=EventMetadata)
    provider_metadata: ProviderMetadata = Field(default_factory=ProviderMetadata)


class InboundMessageEvent(BaseMessageEvent):
    """LeanCloud → Webhook inbound event."""

    event_type: Literal["inbound_message"] = Field(default="inbound_message", frozen=True)
    msg_id_client: str = Field(..., description="Client-generated ID for deduplication")
    msg_id_provider_inbound: str = Field(
        ...,
        description="Provider message ID (e.g., LeanCloud msgId)",
    )


class OutboundMessageEvent(BaseMessageEvent):
    """System/AI → user outbound event."""

    event_type: Literal["outbound_message"] = Field(default="outbound_message", frozen=True)
    msg_id_provider_outbound: Optional[str] = Field(
        default=None,
        description="Outbound provider ID (set after provider send succeeds)",
    )
