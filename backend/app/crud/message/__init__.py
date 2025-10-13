"""
Message system CRUD operations module.

This module imports all message-related CRUD operations.
"""

# Message CRUD
from .message import CRUDMessage, message

# Message failure CRUD
from .failure import CRUDMessageFailure, message_failure

# Media file CRUD
from .media import CRUDMediaFile, media_file

# Export all message CRUD classes and instances
__all__ = [
    # Classes
    "CRUDMessage",
    "CRUDMessageFailure",
    "CRUDMediaFile",
    # Instances
    "message",
    "message_failure",
    "media_file",
]
