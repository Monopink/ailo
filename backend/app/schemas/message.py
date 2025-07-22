from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class MessageTypeEnum(str, Enum):
    """Message type enumeration"""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class MessageStatusEnum(str, Enum):
    """Message status enumeration"""

    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class MessageCreate(BaseModel):
    """Schema for creating a message"""

    content: str = Field(..., min_length=1, max_length=1000, description="Message content")
    message_type: MessageTypeEnum = Field(default=MessageTypeEnum.USER, description="Type of message")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional message metadata")


class MessageUpdate(BaseModel):
    """Schema for updating message status"""

    status: MessageStatusEnum = Field(..., description="New message status")


class MessageResponse(BaseModel):
    """Schema for message response"""

    id: int = Field(..., description="Message ID")
    user_entity_id: str = Field(..., description="User's entity ID")
    bot_entity_id: str = Field(..., description="Bot's entity ID")
    content: str = Field(..., description="Message content")
    message_type: MessageTypeEnum = Field(..., description="Type of message")
    status: MessageStatusEnum = Field(..., description="Message status")
    created_at: datetime = Field(..., description="Message creation timestamp")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional message metadata")

    class Config:
        from_attributes = True


class ConversationHistoryResponse(BaseModel):
    """Schema for conversation history response"""

    messages: list[MessageResponse] = Field(..., description="List of messages in conversation")
    total_count: int = Field(..., description="Total number of messages")
    has_more: bool = Field(..., description="Whether there are more messages")

    class Config:
        from_attributes = True


class MessageSendRequest(BaseModel):
    """Schema for sending a message to a bot"""

    bot_entity_id: str = Field(..., description="Target bot's entity ID")
    content: str = Field(..., min_length=1, max_length=1000, description="Message content")
    conversation_context: Optional[Dict[str, Any]] = Field(None, description="Conversation context")


class MessageSendResponse(BaseModel):
    """Schema for message send response"""

    message_id: int = Field(..., description="Sent message ID")
    bot_response: Optional[str] = Field(None, description="Bot's response message")
    status: MessageStatusEnum = Field(..., description="Message status")
    timestamp: datetime = Field(..., description="Response timestamp")

    class Config:
        from_attributes = True
