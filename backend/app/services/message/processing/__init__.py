"""
Message processing layer.

Handles buffering and rate limiting.
"""

from .buffer import add_message_to_buffer, process_buffered_messages

__all__ = [
    "add_message_to_buffer",
    "process_buffered_messages",
]
