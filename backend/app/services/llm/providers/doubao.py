"""
Doubao (ByteDance) LLM provider implementation.

This module provides functions for interacting with Doubao API.
Supports structured output, thinking mode, and streaming according to Doubao API documentation.
"""

import json
import asyncio
from typing import Dict, Any, Optional, List
import httpx

from models.llm import LLMConfig, LLMProvider
from services.llm.utils import get_provider_api_key, get_provider_base_url
from utils.logging import get_logger

logger = get_logger(__name__)


async def doubao_chat_completion(
    config: LLMConfig,
    provider: LLMProvider,
    messages: List[Dict[str, str]],
    json_schema: Optional[Dict[str, Any]] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    enable_thinking: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Send chat completion request to Doubao API.

    Args:
        config: LLM configuration
        provider: LLM provider information
        messages: List of message objects with 'role' and 'content'
        json_schema: Optional JSON schema for structured output
        temperature: Override temperature setting
        max_tokens: Override max tokens setting
        enable_thinking: Override thinking mode setting

    Returns:
        Dictionary containing response data and metadata
    """
    try:
        # Build request payload
        payload = _build_doubao_payload(
            config, provider, messages, json_schema, temperature, max_tokens, enable_thinking
        )

        # Send request with retries
        response_data = await _send_doubao_request(config, provider, payload)

        # Parse response
        result = _parse_doubao_response(response_data)

        # Include request payload in result for logging
        result["request_payload"] = payload

        return result

    except Exception as e:
        logger.error("doubao_chat_completion_error", error=str(e))
        return {
            "success": False,
            "error": str(e),
            "response": None,
            "usage": None,
            "request_payload": None,
        }


def _build_doubao_payload(
    config: LLMConfig,
    provider: LLMProvider,
    messages: List[Dict[str, str]],
    json_schema: Optional[Dict[str, Any]],
    temperature: Optional[float],
    max_tokens: Optional[int],
    enable_thinking: Optional[bool],
) -> Dict[str, Any]:
    """Build request payload for Doubao API according to official documentation."""
    # Validate required model parameter
    model = config.model_name or provider.default_model
    if not model:
        raise ValueError("Model name is required for Doubao API")

    # Build base payload
    payload = {
        "model": model,
        "messages": messages,
    }

    # Add optional parameters with proper defaults
    if temperature is not None:
        payload["temperature"] = float(temperature)
    elif config.temperature is not None:
        payload["temperature"] = float(config.temperature)

    if max_tokens is not None:
        payload["max_tokens"] = int(max_tokens)
    elif config.max_tokens is not None:
        payload["max_tokens"] = int(config.max_tokens)

    # Add structured output support according to Doubao documentation
    if json_schema and provider.supports_json_schema:
        if config.json_schema_mode == "strict":
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "ai_response", "schema": json_schema, "strict": True},
            }
        elif config.json_schema_mode == "auto":
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "ai_response", "schema": json_schema, "strict": False},
            }
        # For disabled mode, don't add response_format

    # Add thinking mode support according to Doubao documentation
    if provider.supports_thinking:
        thinking_enabled = enable_thinking if enable_thinking is not None else config.enable_thinking
        payload["thinking"] = {"type": "enabled" if thinking_enabled else "disabled"}

    return payload


async def _send_doubao_request(
    config: LLMConfig, provider: LLMProvider, payload: Dict[str, Any]
) -> Dict[str, Any]:
    """Send HTTP request to Doubao API with retries according to official documentation."""
    # Get API key using naming convention
    api_key = get_provider_api_key(provider)

    # Build headers according to Doubao documentation
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    # Get base URL (can be overridden by environment variable)
    base_url = get_provider_base_url(provider)
    if not base_url:
        raise ValueError(f"Base URL not configured for provider: {provider.name}")

    # Build URL - ensure proper format according to Doubao documentation
    base_url = base_url.rstrip("/")
    if not base_url.endswith("/api/v3"):
        if base_url.endswith("/"):
            base_url = base_url[:-1]
        url = f"{base_url}/api/v3/chat/completions"
    else:
        url = f"{base_url}/chat/completions"

    # Send request with timeout and retries
    async with httpx.AsyncClient() as client:
        for attempt in range(config.max_retries + 1):
            try:
                response = await client.post(
                    url, json=payload, headers=headers, timeout=config.timeout_seconds
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    error_text = response.text
                    logger.warning(
                        "doubao_request_failed",
                        status_code=response.status_code,
                        response=error_text[:500],  # Limit log size
                        attempt=attempt + 1,
                    )

                    # Don't retry on client errors (4xx)
                    if 400 <= response.status_code < 500:
                        raise ValueError(f"Doubao API client error {response.status_code}: {error_text}")

                    if attempt < config.max_retries:
                        await asyncio.sleep(2**attempt)  # Exponential backoff
                    else:
                        raise ValueError(f"Doubao API error {response.status_code}: {error_text}")

            except httpx.TimeoutException:
                logger.warning(
                    "doubao_request_timeout", attempt=attempt + 1, timeout=config.timeout_seconds
                )
                if attempt < config.max_retries:
                    await asyncio.sleep(2**attempt)
                else:
                    raise TimeoutError(f"Doubao request timeout after {config.max_retries + 1} attempts")

            except (httpx.ConnectError, httpx.NetworkError) as e:
                logger.warning("doubao_network_error", error=str(e), attempt=attempt + 1)
                if attempt < config.max_retries:
                    await asyncio.sleep(2**attempt)
                else:
                    raise ConnectionError(f"Doubao network error: {str(e)}")

            except Exception as e:
                # Don't retry on unexpected errors
                raise RuntimeError(f"Doubao request unexpected error: {str(e)}")

    raise RuntimeError("Doubao request failed after all retries")


def _parse_doubao_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """Parse Doubao API response according to official documentation."""
    try:
        # Validate response structure
        if not isinstance(data, dict):
            raise ValueError("Response is not a valid JSON object")

        if "choices" not in data or not data["choices"]:
            return {
                "success": False,
                "error": "No choices in Doubao response",
                "response": None,
                "usage": data.get("usage", {}),
            }

        choice = data["choices"][0]
        message = choice.get("message", {})
        content = message.get("content", "")

        # Extract thinking content if present (for thinking mode)
        reasoning_content = message.get("reasoning_content")

        # Parse content based on type
        parsed_content = content
        if content and content.strip().startswith(("{", "[")):
            try:
                parsed_content = json.loads(content)
            except json.JSONDecodeError as e:
                logger.warning("doubao_json_parse_failed", content_preview=content[:100], error=str(e))
                # Keep as string if JSON parsing fails

        # Build response according to project interface
        result = {
            "success": True,
            "response": parsed_content,
            "raw_content": content,
            "usage": data.get("usage", {}),
            "model": data.get("model"),
            "finish_reason": choice.get("finish_reason"),
        }

        # Add thinking content if present
        if reasoning_content:
            result["reasoning_content"] = reasoning_content

        return result

    except Exception as e:
        logger.error(
            "doubao_response_parse_error",
            error=str(e),
            data_keys=list(data.keys()) if isinstance(data, dict) else "not_dict",
        )
        return {
            "success": False,
            "error": f"Failed to parse Doubao response: {str(e)}",
            "response": None,
            "usage": None,
        }
