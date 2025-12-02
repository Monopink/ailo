"""
Message provider factory.

This module provides factory functions for creating message provider instances
based on configuration.
"""

import os

from sqlalchemy.ext.asyncio import AsyncSession

from .base import MessageProvider
from .leancloud import create_leancloud_provider


def create_message_provider(db: AsyncSession, provider_type: str | None = None) -> MessageProvider:
    """
    Create message provider instance.

    Args:
        db: Database session for configuration access
        provider_type: Provider type ("leancloud").
                      If None, uses default from config.

    Returns:
        MessageProvider instance
    """
    if provider_type is None:
        provider_type = os.getenv("DEFAULT_MESSAGE_PROVIDER", "leancloud")

    # Type assertion since we know provider_type is not None after the check
    assert provider_type is not None
    if provider_type == "leancloud":
        return create_leancloud_provider(db)

    raise ValueError(f"Unsupported provider type: {provider_type}")


def get_default_provider(db: AsyncSession) -> MessageProvider:
    """
    Get the default provider based on configuration.

    Returns:
        MessageProvider instance
    """
    return create_message_provider(db)
