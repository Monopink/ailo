"""Message system models module.

This module imports all message-related SQLAlchemy models.
"""

# Media models
from .media import MediaFile

# Message models
from .message import MessageHistory

# Notification models
from .notification import NotificationPushHistory
from .routing import MessageDelivery, MessageDevice, MessageDispatchOutbox, MessageEndpoint

# Export all message models
__all__ = [
    # Message
    "MessageHistory",
    "MessageDevice",
    "MessageEndpoint",
    "MessageDelivery",
    "MessageDispatchOutbox",
    # Media
    "MediaFile",
    # Notification
    "NotificationPushHistory",
]
