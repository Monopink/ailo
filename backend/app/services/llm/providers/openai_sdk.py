"""
OpenAI SDK implementation for LLM providers.

This module provides a unified implementation using the OpenAI Python SDK,
which is compatible with multiple providers including:
- OpenAI GPT models
- Doubao models (OpenAI-compatible)
- DeepSeek models (OpenAI-compatible)
- Qwen models (OpenAI-compatible)
- Any other OpenAI-compatible API
"""

import os
from typing import Dict, Any, List, Optional
from openai import AsyncOpenAI

from models.llm import LLMConfig, LLMProvider
from exceptions.llm import LLMConfigurationError, LLMRequestError, LLMTimeoutError
from utils.logging import get_logger

logger = get_logger(__name__)


async def chat_completion(
    config: LLMConfig,
    provider: LLMProvider,
    messages: List[Dict[str, str]],
    json_schema: Optional[Dict[str, Any]] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    enable_thinking: Optional[bool] = None,
    timeout: Optional[int] = None,
    provider_overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Send chat completion request using OpenAI SDK.

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
        LLMConfigurationError: Configuration error
        LLMRequestError: Request error
        LLMTimeoutError: Timeout error
    """
    # Get API key from environment variable
    api_key = _get_api_key(provider)
    if not api_key:
        raise LLMConfigurationError(
            f"API key not configured for provider: {provider.display_name}. "
            f"Please set environment variable: {provider.api_key_env or f'{provider.name.upper()}_API_KEY'}"
        )

    # Initialize OpenAI client
    client = AsyncOpenAI(
        base_url=provider.base_url,
        api_key=api_key,
        timeout=timeout or config.timeout_seconds or 60,
    )

    # Prepare standard parameters
    params = {
        "model": config.model_name or provider.default_model,
        "messages": messages,
    }

    # Add temperature
    if temperature is not None:
        params["temperature"] = temperature
    elif config.temperature is not None:
        params["temperature"] = float(config.temperature)

    # Add max_tokens
    if max_tokens is not None:
        params["max_tokens"] = max_tokens
    elif config.max_tokens is not None:
        params["max_tokens"] = config.max_tokens

    # Add JSON schema if provided
    if json_schema:
        # Determine strict mode based on config
        # Default to True if not specified for better reliability
        strict_mode = True
        if hasattr(config, "json_schema_mode"):
            strict_mode = config.json_schema_mode == "strict"

        params["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "ai_response", "schema": json_schema, "strict": strict_mode},
        }

    # Add provider-specific parameters via extra_body
    extra_body = _build_extra_body(provider, enable_thinking, config)
    if extra_body:
        params["extra_body"] = extra_body

    # Log request with detailed parameters
    logger.info(
        f"Sending chat completion request to {provider.display_name}",
        extra={
            "provider": provider.name,
            "model": params["model"],
            "message_count": len(messages),
            "has_response_format": "response_format" in params,
            "response_format": params.get("response_format"),
            "has_extra_body": "extra_body" in params,
        },
    )

    try:
        # Send request
        response = await client.chat.completions.create(**params)

        # Extract content and message for logging
        message = response.choices[0].message
        content = message.content

        # Log response with detailed information
        logger.info(
            f"Received chat completion response from {provider.display_name}",
            extra={
                "provider": provider.name,
                "model": response.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
                "message_role": message.role,
                "content_type": type(content).__name__,
                "content_length": len(content) if content else 0,
                "content_preview": content[:200] if content else None,
                "has_refusal": hasattr(message, "refusal") and message.refusal is not None,
                "finish_reason": response.choices[0].finish_reason,
            },
        )

        # Convert response to dict for storage
        raw_response = {
            "id": response.id,
            "object": response.object,
            "created": response.created,
            "model": response.model,
            "choices": [
                {
                    "index": choice.index,
                    "message": {
                        "role": choice.message.role,
                        "content": choice.message.content,
                    },
                    "finish_reason": choice.finish_reason,
                }
                for choice in response.choices
            ],
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
        }

        # Return standardized response with raw data
        return {
            "content": response.choices[0].message.content,
            "model": response.model,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            "finish_reason": response.choices[0].finish_reason,
            "raw_response": raw_response,  # Include full OpenAI API response
            "request_params": params,  # Include request parameters
        }

    except TimeoutError as e:
        # Get the actual timeout value used
        timeout_value = timeout or config.timeout_seconds or 60
        logger.error(
            f"Timeout error from {provider.display_name}: {str(e)}",
            extra={"provider": provider.name, "timeout_seconds": timeout_value},
        )
        raise LLMTimeoutError(
            timeout_seconds=timeout_value,
            provider=provider.name,
            message=f"Request timeout after {timeout_value} seconds: {str(e)}",
        ) from e

    except Exception as e:
        logger.error(
            f"Request error from {provider.display_name}: {str(e)}",
            extra={"provider": provider.name},
        )
        raise LLMRequestError(f"Request failed: {str(e)}") from e


def _get_api_key(provider: LLMProvider) -> Optional[str]:
    """
    Get API key from environment variable.

    Priority:
    1. Use provider.api_key_env if specified
    2. Use default naming: {PROVIDER_NAME}_API_KEY

    Args:
        provider: LLM provider

    Returns:
        API key or None if not found
    """
    # 1. Try custom environment variable name
    if provider.api_key_env:
        api_key = os.getenv(provider.api_key_env)
        if api_key:
            logger.debug(
                f"Using API key from custom environment variable: {provider.api_key_env}",
                extra={"provider": provider.name},
            )
            return api_key

    # 2. Try default naming convention
    default_env_name = f"{provider.name.upper()}_API_KEY"
    api_key = os.getenv(default_env_name)
    if api_key:
        logger.debug(
            f"Using API key from default environment variable: {default_env_name}",
            extra={"provider": provider.name},
        )
        return api_key

    return None


def _build_extra_body(
    provider: LLMProvider,
    enable_thinking: Optional[bool],
    config: LLMConfig,
) -> Optional[Dict[str, Any]]:
    """
    Build extra_body parameters based on provider.

    This is where we handle provider-specific features that are not part of
    the OpenAI standard API.

    Args:
        provider: LLM provider
        enable_thinking: Optional thinking mode override
        config: LLM configuration

    Returns:
        extra_body dict or None
    """
    extra_body = {}

    # Doubao-specific parameters
    if provider.name == "doubao":
        # Thinking mode
        if enable_thinking is not None:
            thinking_type = "enabled" if enable_thinking else "disabled"
            extra_body["thinking"] = {"type": thinking_type}
        elif config.enable_thinking:
            extra_body["thinking"] = {"type": "auto"}

    # Qwen-specific parameters
    elif provider.name == "qwen":
        # Add Qwen-specific features here if needed
        pass

    # DeepSeek-specific parameters
    elif provider.name == "deepseek":
        # Add DeepSeek-specific features here if needed
        pass

    return extra_body if extra_body else None
