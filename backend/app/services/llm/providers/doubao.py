"""
Doubao (ByteDance) LLM provider implementation.

This module provides functions for interacting with Doubao API.
Supports structured output, thinking mode, and streaming according to Doubao API documentation.
"""

import json
from typing import Dict, Any, Optional, List
import httpx

from models.llm import LLMConfig, LLMProvider
from services.llm.utils import get_provider_api_key, get_provider_base_url
from utils.logging import get_logger
from exceptions.llm import (
    LLMEndpointNotFoundError,
    LLMAuthenticationError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMNetworkError,
    LLMServiceError,
    LLMConfigurationError,
)

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
    payload = None
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

    except (
        LLMEndpointNotFoundError,
        LLMAuthenticationError,
        LLMRateLimitError,
        LLMTimeoutError,
        LLMNetworkError,
        LLMServiceError,
    ) as e:
        # LLM-specific exceptions - already formatted
        logger.error("doubao_llm_error", error_code=e.error_code, error=str(e), details=e.details)
        return {
            "success": False,
            "error": str(e),
            "error_code": e.error_code,
            "response": None,
            "usage": None,
            "request_payload": payload,
        }

    except Exception as e:
        # Unexpected errors
        logger.error("doubao_unexpected_error", error=str(e), exc_info=True)
        return {
            "success": False,
            "error": f"Doubao API请求异常: {str(e)}",
            "error_code": "UNKNOWN_ERROR",
            "response": None,
            "usage": None,
            "request_payload": payload,
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
    """Send HTTP request to Doubao API with comprehensive error handling."""

    # Get API key
    try:
        api_key = get_provider_api_key(provider)
    except ValueError as e:
        raise LLMAuthenticationError(
            provider=provider.name, message=str(e), details={"env_key": f"{provider.name.upper()}_API_KEY"}
        )

    # Build headers
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    # Get base URL
    base_url = get_provider_base_url(provider)
    if not base_url:
        raise LLMConfigurationError(
            message=f"Base URL未配置: {provider.name}", details={"provider": provider.name}
        )

    # Build full URL
    base_url = base_url.rstrip("/")
    if not base_url.endswith("/api/v3"):
        base_url = f"{base_url}/api/v3"
    url = f"{base_url}/chat/completions"

    # Send request with error handling
    try:
        async with httpx.AsyncClient(timeout=config.timeout_seconds) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()

    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code
        error_body = e.response.text

        # Parse error response
        try:
            error_data = json.loads(error_body)
            error_message = error_data.get("error", {}).get("message", error_body)
            error_code = error_data.get("error", {}).get("code", "UNKNOWN")
        except Exception:
            error_message = error_body
            error_code = "PARSE_ERROR"

        # Categorize and raise specific exceptions
        if status_code == 404:
            raise LLMEndpointNotFoundError(
                endpoint=payload.get("model", "unknown"),
                provider=provider.name,
                details={
                    "error_code": error_code,
                    "error_message": error_message,
                    "status_code": status_code,
                },
            )

        elif status_code == 401:
            raise LLMAuthenticationError(
                provider=provider.name,
                details={
                    "error_code": error_code,
                    "error_message": error_message,
                },
            )

        elif status_code == 429:
            raise LLMRateLimitError(
                provider=provider.name,
                details={
                    "error_code": error_code,
                    "error_message": error_message,
                },
            )

        elif status_code >= 500:
            raise LLMServiceError(
                message=f"Doubao服务器错误 ({status_code})",
                provider=provider.name,
                error_code=error_code,
                details={
                    "status_code": status_code,
                    "error_message": error_message,
                },
            )

        else:
            raise LLMServiceError(
                message=f"Doubao API请求失败 ({status_code}): {error_message}",
                provider=provider.name,
                error_code=error_code,
                details={
                    "status_code": status_code,
                    "error_message": error_message,
                },
            )

    except httpx.TimeoutException as e:
        raise LLMTimeoutError(
            timeout_seconds=config.timeout_seconds, provider=provider.name, details={"error": str(e)}
        )

    except httpx.NetworkError as e:
        raise LLMNetworkError(
            provider=provider.name,
            message="无法连接到Doubao API。请检查网络连接和Base URL配置。",
            details={"error": str(e), "url": url},
        )

    except Exception as e:
        raise LLMServiceError(
            message=f"Doubao请求异常: {str(e)}",
            provider=provider.name,
            error_code="UNEXPECTED_ERROR",
            details={"error": str(e), "error_type": type(e).__name__},
        )


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
            "raw_response": data,  # Store original API response
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
