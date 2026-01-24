"""Offline message schemas."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.type_defs import JSONDict


class OfflineCursorCreate(BaseModel):
    """Create schema for offline cursor records."""

    user_id: int
    user_qiao_id: str
    device_id: str
    last_ack_msg_id: str | None = None
    last_ack_sent_at: datetime | None = None
    last_pull_at: datetime | None = None


class OfflineCursorUpdate(BaseModel):
    """Update schema for offline cursor records."""

    last_ack_msg_id: str | None = None
    last_ack_sent_at: datetime | None = None
    last_pull_at: datetime | None = None


class OfflineMessageItem(BaseModel):
    """Offline message payload item."""

    msg_id_server: str
    msg_id_client: str | None = None
    conv_id: str
    from_qiao_id: str
    to_qiao_id: str
    content: str | None = None
    message_type: int
    sent_time: int
    server_time: int
    action: JSONDict | None = None
    notification_type: int | None = None
    data: JSONDict | None = None


class OfflineMessagesResponse(BaseModel):
    """Offline messages response payload."""

    server_time_ms: int = Field(..., description="Server time in milliseconds")
    limit: int = Field(..., description="Effective page size")
    has_more: bool = Field(..., description="Whether more messages are available")
    next_cursor: str | None = Field(None, description="Pagination cursor for next page")
    messages: list[OfflineMessageItem]


class OfflineMessageAckRequest(BaseModel):
    """Offline message ACK request payload."""

    device_id: str = Field(..., description="Device/installation UUID")
    last_ack_msg_id: str = Field(..., description="Last acknowledged server message ID")
    last_ack_sent_at: int = Field(..., description="Last acknowledged sent_time in ms")


class OfflineMessageAckResponse(BaseModel):
    """Offline message ACK response payload."""

    success: bool
    server_time_ms: int = Field(..., description="Server time in milliseconds")
