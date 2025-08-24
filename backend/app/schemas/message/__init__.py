"""
Message system schemas module.

This module imports all message-related Pydantic schemas.
"""

# Message schemas
from .message import (
    MessageBase,
    MessageSend,
    MessageResponse,
    MessageListResponse,
    MessageUpdate,
    MessageHistoryRequest,
    ConversationListRequest,
    ConversationInfo,
    MessageFailureResponse,
    BatchMessageUpdate,
    BatchMessageDelete,
)

# Media schemas
from .media import (
    MediaFileBase,
    MediaFileUpload,
    MediaFileResponse,
    MediaFileListResponse,
    MediaFileUpdate,
    MediaFileQuery,
    MediaFileStats,
)

# Emoticon schemas
from .emoticon import (
    EmoticonBase,
    EmoticonCreate,
    EmoticonUpdate,
    EmoticonResponse,
    EmoticonListResponse,
    EmoticonQuery,
    EmoticonSearch,
    EmoticonStats,
)

# Export all message schemas
__all__ = [
    # Message
    "MessageBase",
    "MessageSend",
    "MessageResponse",
    "MessageListResponse",
    "MessageUpdate",
    "MessageHistoryRequest",
    "ConversationListRequest",
    "ConversationInfo",
    "MessageFailureResponse",
    "BatchMessageUpdate",
    "BatchMessageDelete",
    # Media
    "MediaFileBase",
    "MediaFileUpload",
    "MediaFileResponse",
    "MediaFileListResponse",
    "MediaFileUpdate",
    "MediaFileQuery",
    "MediaFileStats",
    # Emoticon
    "EmoticonBase",
    "EmoticonCreate",
    "EmoticonUpdate",
    "EmoticonResponse",
    "EmoticonListResponse",
    "EmoticonQuery",
    "EmoticonSearch",
    "EmoticonStats",
]
