"""
LLM provider factory.

This module provides SDK selection and routing logic.
"""

from typing import Dict, Any, List

from models.llm import LLMConfig, LLMProvider
from utils.logging import get_logger

logger = get_logger(__name__)

# Provider to SDK mapping (code-level configuration)
# This allows flexible switching between different SDK implementations
PROVIDER_SDK_MAP = {
    "doubao": "openai_sdk",  # Doubao uses OpenAI SDK (compatible)
    "openai": "openai_sdk",  # OpenAI uses OpenAI SDK
    "qwen": "openai_sdk",  # Qwen uses OpenAI SDK (compatible)
    "deepseek": "openai_sdk",  # DeepSeek uses OpenAI SDK (compatible)
    "claude": "anthropic_sdk",  # Claude uses Anthropic SDK (not implemented yet)
    "mock": "mock",  # Mock uses mock implementation
}


async def chat_completion(
    config: LLMConfig,
    provider: LLMProvider,
    messages: List[Dict[str, str]],
    **kwargs,
) -> Dict[str, Any]:
    """
    Route to appropriate SDK implementation.

    SDK selection is based on PROVIDER_SDK_MAP configuration.

    Args:
        config: LLM configuration
        provider: LLM provider
        messages: List of messages in OpenAI format
        **kwargs: Additional parameters

    Returns:
        {
            "content": str,
            "model": str,
            "usage": {
                "prompt_tokens": int,
                "completion_tokens": int,
                "total_tokens": int,
            },
            "finish_reason": str,
        }

    Raises:
        ValueError: Unsupported SDK
        LLMConfigurationError: Configuration error
        LLMRequestError: Request error
        LLMTimeoutError: Timeout error
    """
    # Get SDK name from configuration
    sdk_name = PROVIDER_SDK_MAP.get(provider.name, "openai_sdk")

    logger.debug(
        f"Routing request to SDK: {sdk_name}",
        extra={
            "provider": provider.name,
            "sdk": sdk_name,
        },
    )

    # Import and call appropriate SDK implementation
    if sdk_name == "openai_sdk":
        from .openai_sdk import chat_completion as sdk_chat
    elif sdk_name == "anthropic_sdk":
        # Not implemented yet
        raise ValueError(f"SDK not implemented: {sdk_name}")
    elif sdk_name == "mock":
        from .mock import chat_completion as sdk_chat
    else:
        raise ValueError(f"Unsupported SDK: {sdk_name}")

    return await sdk_chat(config, provider, messages, **kwargs)
