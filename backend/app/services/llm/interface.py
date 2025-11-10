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
        thinking_mode: Optional[str] = None,
        top_p: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
        presence_penalty: Optional[float] = None,
        stop_sequences: Optional[List[str]] = None,
        extra_params: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
        provider_overrides: Optional[Dict[str, Any]] = None,
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
            thinking_mode: Optional thinking mode override (enabled/disabled/auto)
            top_p: Optional nucleus sampling override
            frequency_penalty: Optional frequency penalty override
            presence_penalty: Optional presence penalty override
            stop_sequences: Optional stop sequences override
            extra_params: Optional provider-specific JSON payload
            timeout: Optional timeout override
            provider_overrides: Optional provider-specific overrides

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
