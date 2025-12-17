"""
Message system schemas module.

This module imports all message-related Pydantic schemas.
"""

# Message schemas removed - not currently used

# Media schemas
from .leancloud import (
    LeanCloudConfigResponse,
    LeanCloudSignatureRequest,
    LeanCloudSignatureResponse,
)
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

# Export all message schemas
__all__ = [
    # LeanCloud
    "LeanCloudConfigResponse",
    "LeanCloudSignatureRequest",
    "LeanCloudSignatureResponse",
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
]
