"""
Doubao (ByteDance) LLM provider implementation.

This module provides functions for interacting with Doubao API.
"""

import json
import asyncio
from typing import Dict, Any, Optional, List
import httpx
import os

from models.llm import LLMConfig, LLMProvider
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

        return result

    except Exception as e:
        logger.error("doubao_chat_completion_error", error=str(e))
        return {"success": False, "error": str(e), "response": None, "usage": None}


def _build_doubao_payload(
    config: LLMConfig,
    provider: LLMProvider,
    messages: List[Dict[str, str]],
    json_schema: Optional[Dict[str, Any]],
    temperature: Optional[float],
    max_tokens: Optional[int],
    enable_thinking: Optional[bool],
) -> Dict[str, Any]:
    """Build request payload for Doubao API."""
    payload = {
        "messages": messages,
        "temperature": temperature or config.temperature or 0.7,
        "max_tokens": max_tokens or config.max_tokens or 2000,
    }

    # Add model
    if config.model_name:
        payload["model"] = config.model_name
    elif provider.default_model:
        payload["model"] = provider.default_model

    # Add JSON schema if provided and supported
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

    # Add thinking mode if supported
    if provider.supports_thinking:
        thinking_enabled = enable_thinking if enable_thinking is not None else config.enable_thinking
        payload["thinking"] = {"type": "enabled" if thinking_enabled else "disabled"}

    return payload


async def _send_doubao_request(
    config: LLMConfig, provider: LLMProvider, payload: Dict[str, Any]
) -> Dict[str, Any]:
    """Send HTTP request to Doubao API with retries."""
    # Get API key from environment
    if not provider.api_key_env:
        raise Exception("API key environment variable not configured")

    api_key = os.getenv(provider.api_key_env)
    if not api_key:
        raise Exception(f"API key not found in environment: {provider.api_key_env}")

    # Build headers
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    # Build URL
    url = f"{provider.base_url}/chat/completions"

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
                    logger.warning(
                        "doubao_request_failed",
                        status_code=response.status_code,
                        response=response.text,
                        attempt=attempt + 1,
                    )

                    if attempt < config.max_retries:
                        await asyncio.sleep(2**attempt)  # Exponential backoff
                    else:
                        response.raise_for_status()

            except httpx.TimeoutException:
                logger.warning("doubao_request_timeout", attempt=attempt + 1)
                if attempt < config.max_retries:
                    await asyncio.sleep(2**attempt)
                else:
                    raise Exception("Doubao request timeout after retries")
            except Exception as e:
                if attempt < config.max_retries:
                    logger.warning("doubao_request_error", error=str(e), attempt=attempt + 1)
                    await asyncio.sleep(2**attempt)
                else:
                    raise

    raise Exception("Doubao request failed after all retries")


def _parse_doubao_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """Parse Doubao API response."""
    try:
        # Extract response content
        if "choices" in data and len(data["choices"]) > 0:
            choice = data["choices"][0]
            content = choice.get("message", {}).get("content", "")

            # Try to parse as JSON if it looks like JSON
            parsed_content = content
            if content.strip().startswith(("{", "[")):
                try:
                    parsed_content = json.loads(content)
                except json.JSONDecodeError:
                    # Keep as string if JSON parsing fails
                    pass

            return {
                "success": True,
                "response": parsed_content,
                "raw_content": content,
                "usage": data.get("usage", {}),
                "model": data.get("model"),
                "finish_reason": choice.get("finish_reason"),
            }
        else:
            return {
                "success": False,
                "error": "No valid response in Doubao output",
                "response": None,
                "usage": data.get("usage", {}),
            }

    except Exception as e:
        logger.error("doubao_response_parse_error", error=str(e))
        return {
            "success": False,
            "error": f"Failed to parse Doubao response: {str(e)}",
            "response": None,
            "usage": None,
        }
