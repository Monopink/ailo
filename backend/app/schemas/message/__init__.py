"""Message system schemas module.

This module imports all message-related Pydantic schemas.
"""

# Message schemas
from .leancloud import (
    LeanCloudBootstrapConfig,
    LeanCloudBootstrapPresence,
    LeanCloudBootstrapRequest,
    LeanCloudBootstrapResponse,
    LeanCloudBootstrapSignature,
)

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

# Export all message schemas
__all__ = [
    # Message session
    "LeanCloudBootstrapRequest",
    "LeanCloudBootstrapResponse",
    "LeanCloudBootstrapConfig",
    "LeanCloudBootstrapPresence",
    "LeanCloudBootstrapSignature",
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
]
