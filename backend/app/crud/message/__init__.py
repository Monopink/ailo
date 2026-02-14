"""Message system CRUD operations module.

This module imports all message-related CRUD operations.
"""

# Media file CRUD
from .media import CRUDMediaFile, media_file

# Message CRUD
from .message import CRUDMessage, message

# Notification CRUD
from .notification import CRUDNotificationPushHistory, notification_push_history

# Export all message CRUD classes and instances
__all__ = [
    # Classes
    "CRUDMessage",
    "CRUDMediaFile",
    "CRUDNotificationPushHistory",
    # Instances
    "message",
    "media_file",
    "notification_push_history",
]
