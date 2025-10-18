"""
Message provider factory.

This module provides factory functions for creating message provider instances
based on configuration.
"""

import os
from typing import Dict, Optional
from .base import MessageProvider


class MessageProviderFactory:
    """Factory for creating message provider instances."""

    _providers: Dict[str, MessageProvider] = {}

    @classmethod
    def create_provider(cls, provider_type: str) -> MessageProvider:
        """
        Create or get cached provider instance.

        Args:
            provider_type: Provider type string ("leancloud", "internal")

        Returns:
            MessageProvider instance

        Raises:
            ValueError: If provider type is not supported
        """
        if provider_type in cls._providers:
            return cls._providers[provider_type]

        if provider_type == "leancloud":
            from .leancloud import create_leancloud_provider

            provider = create_leancloud_provider()
        else:
            raise ValueError(f"Unsupported provider type: {provider_type}")

        cls._providers[provider_type] = provider
        return provider

    @classmethod
    def clear_cache(cls):
        """Clear provider cache (useful for testing)."""
        cls._providers.clear()


def create_message_provider(provider_type: Optional[str] = None) -> MessageProvider:
    """
    Create message provider instance.

    Args:
        provider_type: Provider type ("leancloud").
                      If None, uses default from config.

    Returns:
        MessageProvider instance
    """
    if provider_type is None:
        provider_type = os.getenv("DEFAULT_MESSAGE_PROVIDER", "leancloud")

    # Type assertion since we know provider_type is not None after the check
    assert provider_type is not None
    return MessageProviderFactory.create_provider(provider_type)


def get_default_provider() -> MessageProvider:
    """
    Get the default provider based on configuration.

    Returns:
        MessageProvider instance
    """
    return create_message_provider()


def clear_provider_cache():
    """Clear provider cache (useful for testing)."""
    MessageProviderFactory.clear_cache()
