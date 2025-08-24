"""
Message related schemas.

This module contains Pydantic schemas for messages and conversations.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, validator

from enums import MessageDirection, MessageParticipantType, ServiceProvider, MessageType, MessageStatus
from schemas.common import BaseSchema


# Message Schemas


class MessageBase(BaseSchema):
    """Base message schema with common fields."""

    conversation_id: str = Field(..., max_length=32, description="Conversation ID")
    message_type: MessageType = Field(..., description="Message type")
    content: Optional[str] = Field(None, description="Message content")


class MessageSend(BaseModel):
    """Schema for sending a message."""

    conversation_id: str = Field(..., max_length=32, description="Conversation ID")
    message_type: MessageType = Field(MessageType.TEXT, description="Message type")
    content: Optional[str] = Field(None, max_length=1000, description="Message content")
    client_sent_time: Optional[datetime] = Field(None, description="Client-side sent time")
    msg_id_client: Optional[str] = Field(None, max_length=64, description="Client message ID")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Message metadata")

    @validator("content")
    def validate_content_by_type(cls, v, values):
        """Validate content based on message type."""
        message_type = values.get("message_type")
        if message_type == MessageType.TEXT and not v:
            raise ValueError("Content is required for text messages")
        if message_type == MessageType.SYSTEM and not v:
            raise ValueError("Content is required for system messages")
        return v


class MessageResponse(MessageBase):
    """Schema for message response data."""

    msg_id_server: str = Field(..., description="Server message ID")
    msg_id_provider: Optional[str] = Field(None, description="Third-party service message ID")
    msg_id_client: Optional[str] = Field(None, description="Client message ID")
    direction: MessageDirection = Field(..., description="Message direction")
    platform: Optional[int] = Field(None, description="Platform")
    client_sent_time: Optional[datetime] = Field(None, description="Client-side sent time")
    from_type: MessageParticipantType = Field(..., description="Sender type")
    from_id: int = Field(..., description="Sender internal ID")
    from_qiao_id: str = Field(..., description="Sender external ID")
    to_type: MessageParticipantType = Field(..., description="Receiver type")
    to_id: int = Field(..., description="Receiver internal ID")
    to_qiao_id: str = Field(..., description="Receiver external ID")
    service_provider: ServiceProvider = Field(..., description="Service provider")
    status: MessageStatus = Field(..., description="Message status")
    message_metadata: Optional[Dict[str, Any]] = Field(None, description="Message metadata")
    created_at: datetime = Field(..., description="Message creation time")


class MessageListResponse(BaseSchema):
    """Schema for message list item (minimal info)."""

    msg_id_server: str = Field(..., description="Server message ID")
    conversation_id: str = Field(..., description="Conversation ID")
    message_type: MessageType = Field(..., description="Message type")
    content: Optional[str] = Field(None, description="Message content")
    from_qiao_id: str = Field(..., description="Sender external ID")
    to_qiao_id: str = Field(..., description="Receiver external ID")
    status: MessageStatus = Field(..., description="Message status")
    created_at: datetime = Field(..., description="Message creation time")


class MessageUpdate(BaseModel):
    """Schema for updating message status."""

    status: MessageStatus = Field(..., description="New message status")


# Message History Query Schemas


class MessageHistoryRequest(BaseModel):
    """Schema for querying message history."""

    conversation_id: str = Field(..., max_length=32, description="Conversation ID")
    before_time: Optional[datetime] = Field(None, description="Get messages before this time")
    after_time: Optional[datetime] = Field(None, description="Get messages after this time")
    message_types: Optional[List[MessageType]] = Field(None, description="Filter by message types")
    limit: int = Field(20, ge=1, le=100, description="Maximum number of messages")


class ConversationListRequest(BaseModel):
    """Schema for getting conversation list."""

    include_muted: bool = Field(False, description="Include muted conversations")
    include_blocked: bool = Field(False, description="Include blocked conversations")
    limit: int = Field(20, ge=1, le=100, description="Maximum number of conversations")


class ConversationInfo(BaseSchema):
    """Schema for conversation information."""

    conv_id: str = Field(..., description="Conversation ID")
    contact_qiao_id: str = Field(..., description="Contact external ID")
    contact_type: int = Field(..., description="Contact type")
    alias: Optional[str] = Field(None, description="Contact alias")
    avatar_url: Optional[str] = Field(None, description="Avatar URL")
    last_message: Optional[MessageListResponse] = Field(None, description="Last message")
    unread_count: int = Field(0, description="Unread message count")
    is_pinned: bool = Field(False, description="Is pinned")
    is_muted: bool = Field(False, description="Is muted")
    updated_at: datetime = Field(..., description="Last update time")


# Message Delivery Failure Schemas


class MessageFailureResponse(BaseSchema):
    """Schema for message delivery failure information."""

    msg_id_server: str = Field(..., description="Original message ID")
    from_qiao_id: str = Field(..., description="Sender external ID")
    to_qiao_id: str = Field(..., description="Receiver external ID")
    message_type: MessageType = Field(..., description="Message type")
    content: Optional[str] = Field(None, description="Message content")
    fail_reason_code: Optional[str] = Field(None, description="Failure reason code")
    fail_detail: Optional[str] = Field(None, description="Detailed error information")
    retry_count: int = Field(..., description="Current retry count")
    max_retry_count: int = Field(..., description="Maximum retry count")
    next_retry_at: Optional[datetime] = Field(None, description="Next retry time")
    created_at: datetime = Field(..., description="Failure time")


# Batch Message Operations


class BatchMessageUpdate(BaseModel):
    """Schema for batch updating message status."""

    msg_ids: List[str] = Field(..., min_items=1, max_items=100, description="Message IDs")
    status: MessageStatus = Field(..., description="New status")


class BatchMessageDelete(BaseModel):
    """Schema for batch deleting messages."""

    msg_ids: List[str] = Field(..., min_items=1, max_items=100, description="Message IDs")
    permanent: bool = Field(False, description="Permanent deletion")
