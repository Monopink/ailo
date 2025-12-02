"""
Message storage layer.

Handles message persistence to database.
"""

from .participant_resolver import get_participant_info
from .persistence import store_message

__all__ = [
    "get_participant_info",
    "store_message",
]
