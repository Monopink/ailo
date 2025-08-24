"""
Message system models module.

This module imports all message-related SQLAlchemy models.
"""

# Message models
from .message import MessageHistory, MessageDeliveryFailure

# Media models
from .media import MediaFile

# Emoticon models
from .emoticon import Emoticon

# Export all message models
__all__ = [
    # Message
    "MessageHistory",
    "MessageDeliveryFailure",
    # Media
    "MediaFile",
    # Emoticon
    "Emoticon",
]
