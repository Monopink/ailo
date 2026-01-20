"""
Message storage layer.

Handles message persistence to database.
"""

from .persistence import store_message

__all__ = [
    "store_message",
]
