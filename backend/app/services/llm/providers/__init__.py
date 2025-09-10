"""
LLM providers module.

This module contains provider-specific implementations for different LLM services.
"""

from .doubao import doubao_chat_completion
from .mock import mock_chat_completion

# Provider registry mapping provider names to their functions
PROVIDER_REGISTRY = {
    "doubao": doubao_chat_completion,
    "mock": mock_chat_completion,
}

__all__ = [
    "doubao_chat_completion",
    "mock_chat_completion",
    "PROVIDER_REGISTRY",
]
