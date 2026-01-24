"""Message system models module.

This module imports all message-related SQLAlchemy models.
"""

# Media models
from .media import MediaFile

# Message models
from .message import MessageDeliveryFailure, MessageHistory

# Notification models
from .notification import NotificationPushHistory
from .offline_cursor import MessageOfflineCursor

# Export all message models
__all__ = [
    # Message
    "MessageHistory",
    "MessageDeliveryFailure",
    "MessageOfflineCursor",
    # Media
    "MediaFile",
    # Notification
    "NotificationPushHistory",
]
