"""Message system CRUD operations module.

This module imports all message-related CRUD operations.
"""

# Message failure CRUD
from .failure import CRUDMessageFailure, message_failure

# Media file CRUD
from .media import CRUDMediaFile, media_file

# Message CRUD
from .message import CRUDMessage, message

# Notification CRUD
from .notification import CRUDNotificationPushHistory, notification_push_history
from .offline_cursor import CRUDMessageOfflineCursor, offline_cursor

# Export all message CRUD classes and instances
__all__ = [
    # Classes
    "CRUDMessage",
    "CRUDMessageFailure",
    "CRUDMediaFile",
    "CRUDNotificationPushHistory",
    "CRUDMessageOfflineCursor",
    # Instances
    "message",
    "message_failure",
    "media_file",
    "notification_push_history",
    "offline_cursor",
]
