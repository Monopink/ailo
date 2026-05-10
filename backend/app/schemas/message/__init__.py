"""Message system schemas module.

This module imports all message-related Pydantic schemas.
"""

# Media schemas
from .media import (
    MediaFileBase,
    MediaFileListResponse,
    MediaFileQuery,
    MediaFileResponse,
    MediaFileStats,
    MediaFileUpdate,
    MediaFileUpload,
)

# Notification schemas
from .notification import (
    ContactRequestNotificationData,
    NotificationAction,
    NotificationActionData,
    NotificationData,
)
from .offline import (
    OfflineMessageAckRequest,
    OfflineMessageAckResponse,
    OfflineMessageItem,
    OfflineMessagesResponse,
)
from .ws_session import (
    MessageWSPresencePayload,
    MessageWSSessionAuth,
    MessageWSSessionBootstrapResponse,
    MessageWSSessionPayload,
    MessageWSSessionTicketRequest,
)

# Export all message schemas
__all__ = [
    # Media
    "MediaFileBase",
    "MediaFileUpload",
    "MediaFileResponse",
    "MediaFileListResponse",
    "MediaFileUpdate",
    "MediaFileQuery",
    "MediaFileStats",
    # Notification
    "NotificationAction",
    "NotificationData",
    "NotificationActionData",
    "ContactRequestNotificationData",
    # Offline message
    "OfflineMessageAckRequest",
    "OfflineMessageAckResponse",
    "OfflineMessageItem",
    "OfflineMessagesResponse",
    # WebSocket session bootstrap
    "MessageWSSessionTicketRequest",
    "MessageWSSessionAuth",
    "MessageWSSessionPayload",
    "MessageWSPresencePayload",
    "MessageWSSessionBootstrapResponse",
]
