"""
Message service providers module.

This module provides an abstraction layer for different message service providers,
allowing easy switching between LeanCloud, internal messaging, or other providers.
"""

from .base import MessageProvider, MessageResult
from .factory import create_message_provider, get_default_provider

__all__ = [
    "MessageProvider",
    "MessageResult",
    "create_message_provider",
    "get_default_provider",
]
