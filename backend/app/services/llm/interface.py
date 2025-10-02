"""
LLM provider interface.

This module defines the unified interface that all LLM SDK implementations must follow.
"""

from typing import Dict, Any, List, Optional, Protocol
from models.llm import LLMConfig, LLMProvider


class LLMProviderInterface(Protocol):
    """
    Unified LLM provider interface.

    All SDK implementations must follow this interface to ensure consistency
    and allow flexible switching between different SDKs.
    """

    async def chat_completion(
        self,
        config: LLMConfig,
        provider: LLMProvider,
        messages: List[Dict[str, str]],
        json_schema: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        enable_thinking: Optional[bool] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Send chat completion request.

        Args:
            config: LLM configuration
            provider: LLM provider
            messages: List of messages in OpenAI format
            json_schema: Optional JSON schema for structured output
            temperature: Optional temperature override
            max_tokens: Optional max tokens override
            enable_thinking: Optional thinking mode override
            timeout: Optional timeout override

        Returns:
            {
                "content": str,              # Response content
                "model": str,                # Model name used
                "usage": {
                    "prompt_tokens": int,
                    "completion_tokens": int,
                    "total_tokens": int,
                },
                "finish_reason": str,        # Finish reason (stop, length, etc.)
            }

        Raises:
            LLMConfigurationError: Configuration error
            LLMRequestError: Request error
            LLMTimeoutError: Timeout error
        """
        ...

