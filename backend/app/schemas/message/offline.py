"""Offline message schemas."""

from pydantic import BaseModel, Field

from app.type_defs import JSONDict


class OfflineMessageItemMetadata(BaseModel):
    """Subset of message metadata exposed by offline API."""

    action: JSONDict | None = None
    notification_type: int | None = None


class OfflineMessageItem(BaseModel):
    """Offline message payload item."""

    msg_id_server: str
    msg_id_client: str | None = None
    conversation_id: str
    from_qiao_id: str
    to_qiao_id: str
    content: str | None = None
    message_type: int
    client_sent_time_ms: int | None = None
    sent_time_ms: int
    metadata: OfflineMessageItemMetadata = Field(default_factory=OfflineMessageItemMetadata)


class OfflineMessagesResponse(BaseModel):
    """Offline messages response payload."""

    server_time_ms: int = Field(..., description="Server time in milliseconds")
    limit: int = Field(..., description="Effective page size")
    has_more: bool = Field(..., description="Whether more messages are available")
    next_cursor: str | None = Field(None, description="Pagination cursor for next page")
    messages: list[OfflineMessageItem]


class OfflineMessageAckRequest(BaseModel):
    """Offline message ACK request payload.

    ACK indicates the client has persisted messages up to last_ack_msg_id.
    """

    device_id: str = Field(..., description="Device/installation UUID")
    last_ack_msg_id: str = Field(..., description="Last acknowledged server message ID")


class OfflineMessageAckResponse(BaseModel):
    """Offline message ACK response payload."""

    success: bool
    server_time_ms: int = Field(..., description="Server time in milliseconds")
