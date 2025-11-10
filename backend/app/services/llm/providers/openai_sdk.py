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
from typing import Dict, Any, List, Optional, Callable, Awaitable
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
    thinking_mode: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    top_p: Optional[float] = None,
    frequency_penalty: Optional[float] = None,
    presence_penalty: Optional[float] = None,
    stop_sequences: Optional[List[str]] = None,
    timeout: Optional[int] = None,
    extra_params: Optional[Dict[str, Any]] = None,
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
        thinking_mode: Optional thinking mode override
        top_p: Optional nucleus sampling override
        frequency_penalty: Optional frequency penalty override
        presence_penalty: Optional presence penalty override
        stop_sequences: Optional stop sequences override
        timeout: Optional timeout override
        extra_params: Optional provider-specific parameters stored with config
        provider_overrides: Optional per-request overrides (model_override, extra_body, headers, etc.)

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

    # Initialize OpenAI client with retry support
    client = AsyncOpenAI(
        base_url=provider.base_url,
        api_key=api_key,
        timeout=timeout or config.timeout_seconds or 60,
        max_retries=3,  # Use AsyncOpenAI's built-in retry mechanism
    )

    # Prepare standard parameters
    params = {
        "model": config.model_name or provider.default_model,
        "messages": messages,
    }

    # Add standard parameters (override > config)
    params["temperature"] = temperature if temperature is not None else float(config.temperature) if config.temperature is not None else 0.7
    params["max_tokens"] = max_tokens if max_tokens is not None else config.max_tokens if config.max_tokens is not None else 4000
    params["top_p"] = top_p if top_p is not None else float(config.top_p)
    params["frequency_penalty"] = frequency_penalty if frequency_penalty is not None else float(config.frequency_penalty)
    params["presence_penalty"] = presence_penalty if presence_penalty is not None else float(config.presence_penalty)

    # Add stop sequences (with validation)
    final_stop_sequences = stop_sequences if stop_sequences is not None else config.stop_sequences
    if final_stop_sequences and len(final_stop_sequences) > 0:
        # Validate: max 4 strings
        if len(final_stop_sequences) > 4:
            logger.warning("stop_sequences_too_many", count=len(final_stop_sequences), max=4)
            final_stop_sequences = final_stop_sequences[:4]

        # Check if provider/model supports stop sequences
        # Doubao thinking mode doesn't support stop
        final_thinking_mode = thinking_mode or config.thinking_mode
        if provider.name == "doubao" and final_thinking_mode == "enabled":
            logger.warning("stop_sequences_not_supported_with_thinking", provider=provider.name)
        else:
            params["stop"] = final_stop_sequences

    # Add JSON schema if provided
    if json_schema:
        strict_mode = config.json_schema_mode == "strict" if config.json_schema_mode else True
        params["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "ai_response", "schema": json_schema, "strict": strict_mode},
        }

    # Add provider-specific parameters via extra_body
    extra_body = _build_extra_body(provider, thinking_mode, config, extra_params)
    extra_body = _apply_provider_overrides(params, extra_body, provider_overrides)
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
    thinking_mode: Optional[str],
    config: LLMConfig,
    extra_params: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Build extra_body parameters based on provider.

    This is where we handle provider-specific features that are not part of
    the OpenAI standard API.

    Args:
        provider: LLM provider
        thinking_mode: Optional thinking mode override (enabled/disabled/auto)
        config: LLM configuration
        extra_params: Optional extra parameters override

    Returns:
        extra_body dict or None
    """
    extra_body = {}

    # 1. Merge config.extra_params
    if config.extra_params:
        extra_body.update(config.extra_params)

    # 2. Merge override extra_params (highest priority)
    if extra_params:
        extra_body.update(extra_params)

    # 3. Add thinking mode (Doubao-specific)
    if provider.name == "doubao":
        # Determine thinking mode (override > config)
        final_thinking_mode = thinking_mode or config.thinking_mode

        # Only add thinking parameter if not auto (let model decide)
        if final_thinking_mode != "auto":
            extra_body["thinking"] = {"type": final_thinking_mode}

    # Qwen-specific parameters
    elif provider.name == "qwen":
        # Add Qwen-specific features here if needed
        pass

    # DeepSeek-specific parameters
    elif provider.name == "deepseek":
        # Add DeepSeek-specific features here if needed
        pass

    return extra_body if extra_body else None


def _apply_provider_overrides(
    params: Dict[str, Any],
    extra_body: Optional[Dict[str, Any]],
    provider_overrides: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Apply provider-level override parameters safely.
    """
    if not provider_overrides or not isinstance(provider_overrides, dict):
        return extra_body

    # Model override (highest precedence)
    override_model = provider_overrides.get("model_override") or provider_overrides.get("model")
    if isinstance(override_model, str):
        params["model"] = override_model

    # Allow direct OpenAI params injection via params_override
    manual_params = provider_overrides.get("params_override")
    if isinstance(manual_params, dict):
        params.update(manual_params)

    # Extra headers/query supported by OpenAI SDK
    extra_headers = provider_overrides.get("extra_headers")
    if isinstance(extra_headers, dict):
        params["extra_headers"] = extra_headers

    extra_query = provider_overrides.get("extra_query")
    if isinstance(extra_query, dict):
        params["extra_query"] = extra_query

    # Merge extra_body overrides
    override_extra_body = provider_overrides.get("extra_body")
    if isinstance(override_extra_body, dict):
        if extra_body is None:
            extra_body = dict(override_extra_body)
        else:
            extra_body.update(override_extra_body)

    return extra_body


async def chat_completion_stream(
    config: LLMConfig,
    provider: LLMProvider,
    messages: List[Dict[str, str]],
    preemption_checker: Optional[Callable[[], Awaitable[bool]]] = None,
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
    Send streaming chat completion request using OpenAI SDK with early stop support.

    This function supports preemptive early stopping to save token costs when
    the request is no longer needed (e.g., user sent a new message).

    Args:
        config: LLM configuration
        provider: LLM provider
        messages: List of messages in OpenAI format
        preemption_checker: Optional async function that returns True if request should stop
        json_schema: Optional JSON schema for structured output
        temperature: Optional temperature override
        max_tokens: Optional max tokens override
        thinking_mode: Optional thinking mode override (enabled/disabled/auto)
        top_p: Optional nucleus sampling override
        frequency_penalty: Optional frequency penalty override
        presence_penalty: Optional presence penalty override
        stop_sequences: Optional stop sequences override
        extra_params: Optional provider-specific parameters
        timeout: Optional timeout override
        provider_overrides: Optional provider-specific overrides

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
            "preempted": bool,  # True if stopped early due to preemption
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
        "stream": True,  # Enable streaming
        "stream_options": {"include_usage": True},  # Get usage info in final chunk
    }

    # Add sampling / penalty parameters (override > config)
    params["temperature"] = (
        temperature
        if temperature is not None
        else float(config.temperature)
        if config.temperature is not None
        else 0.7
    )
    params["max_tokens"] = (
        max_tokens if max_tokens is not None else config.max_tokens if config.max_tokens is not None else 4000
    )
    params["top_p"] = top_p if top_p is not None else float(config.top_p)
    params["frequency_penalty"] = (
        frequency_penalty if frequency_penalty is not None else float(config.frequency_penalty)
    )
    params["presence_penalty"] = (
        presence_penalty if presence_penalty is not None else float(config.presence_penalty)
    )

    # Add stop sequences
    final_stop_sequences = stop_sequences if stop_sequences is not None else config.stop_sequences
    if final_stop_sequences:
        if len(final_stop_sequences) > 4:
            logger.warning("stop_sequences_too_many", count=len(final_stop_sequences), max=4)
            final_stop_sequences = final_stop_sequences[:4]

        final_thinking_mode = thinking_mode or config.thinking_mode
        if provider.name == "doubao" and final_thinking_mode == "enabled":
            logger.warning("stop_sequences_not_supported_with_thinking", provider=provider.name)
        else:
            params["stop"] = final_stop_sequences

    # Add JSON schema if provided
    if json_schema:
        strict_mode = True
        if hasattr(config, "json_schema_mode"):
            strict_mode = config.json_schema_mode == "strict"

        params["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "ai_response", "schema": json_schema, "strict": strict_mode},
        }

    # Add provider-specific parameters via extra_body
    extra_body = _build_extra_body(provider, thinking_mode, config, extra_params)
    extra_body = _apply_provider_overrides(params, extra_body, provider_overrides)
    if extra_body:
        params["extra_body"] = extra_body

    # Log request
    logger.info(
        f"Sending streaming chat completion request to {provider.display_name}",
        extra={
            "provider": provider.name,
            "model": params["model"],
            "message_count": len(messages),
            "has_preemption_checker": preemption_checker is not None,
        },
    )

    try:
        # Send streaming request
        stream = await client.chat.completions.create(**params)

        # Accumulate response
        content = ""
        usage = None
        finish_reason = None
        model = None
        preempted = False

        # Process stream chunks
        async for chunk in stream:
            # Check for preemption
            if preemption_checker and await preemption_checker():
                preempted = True
                logger.info(
                    f"Stream preempted for {provider.display_name}",
                    extra={
                        "provider": provider.name,
                        "tokens_received": len(content),
                    },
                )
                break

            # Extract model from first chunk
            if model is None and chunk.model:
                model = chunk.model

            # Accumulate content
            if chunk.choices and len(chunk.choices) > 0:
                delta = chunk.choices[0].delta
                if delta.content:
                    content += delta.content

                # Get finish reason from final content chunk
                if chunk.choices[0].finish_reason:
                    finish_reason = chunk.choices[0].finish_reason

            # Get usage from final chunk (if available)
            if hasattr(chunk, "usage") and chunk.usage:
                usage = {
                    "prompt_tokens": chunk.usage.prompt_tokens,
                    "completion_tokens": chunk.usage.completion_tokens,
                    "total_tokens": chunk.usage.total_tokens,
                }

        # If preempted, finish_reason is "stop" (early stop)
        if preempted:
            finish_reason = "stop"

        # Fallback usage if not provided (estimate)
        if usage is None:
            # Rough estimation: 1 token ≈ 4 characters
            estimated_completion_tokens = len(content) // 4
            usage = {
                "prompt_tokens": 0,  # Unknown
                "completion_tokens": estimated_completion_tokens,
                "total_tokens": estimated_completion_tokens,
            }
            logger.warning(
                f"Usage info not available from {provider.display_name}, using estimation",
                extra={"provider": provider.name, "estimated_tokens": estimated_completion_tokens},
            )

        # Log response
        logger.info(
            f"Received streaming response from {provider.display_name}",
            extra={
                "provider": provider.name,
                "model": model,
                "usage": usage,
                "content_length": len(content),
                "finish_reason": finish_reason,
                "preempted": preempted,
            },
        )

        # Return standardized response
        return {
            "content": content,
            "model": model or params["model"],
            "usage": usage,
            "finish_reason": finish_reason or "stop",
            "preempted": preempted,
            "raw_response": {
                "streaming": True,
                "preempted": preempted,
            },
            "request_params": params,
        }

    except TimeoutError as e:
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
            f"Streaming request error from {provider.display_name}: {str(e)}",
            extra={"provider": provider.name},
        )
        raise LLMRequestError(f"Streaming request failed: {str(e)}") from e
