"""
Mock LLM provider implementation for testing.

This adapter mimics the Responses API behavior so that upstream logic can
be exercised without calling a real provider.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any, Dict

from models.llm import LLMConfig, LLMProvider
from services.llm.types import LLMRequestOptions, LLMProviderResult
from utils.logging import get_logger

logger = get_logger(__name__)


def _build_payload(config: LLMConfig, provider: LLMProvider, options: LLMRequestOptions) -> Dict[str, Any]:
    """Create a payload snapshot to simplify debugging."""

    payload: Dict[str, Any] = {
        "model": options.model or config.model_name or provider.default_model or "mock-model-v1",
        "messages": options.messages,
        "temperature": (
            options.temperature
            if options.temperature is not None
            else (float(config.temperature) if config.temperature is not None else 0.7)
        ),
        "max_tokens": options.max_tokens if options.max_tokens is not None else config.max_tokens or 1024,
        "thinking_mode": options.thinking_mode or config.thinking_mode,
        "tools": options.tools,
        "tool_choice": options.tool_choice,
        "max_tool_calls": options.max_tool_calls,
        "extra_headers": options.extra_headers,
        "extra_query": options.extra_query,
        "extra_body": options.extra_body,
        "caching": {
            "enabled": options.caching.enabled,
            "strategy": options.caching.strategy,
            "previous_response_id": options.caching.previous_response_id,
        },
    }

    if options.stop_sequences:
        payload["stop"] = options.stop_sequences

    if options.json_schema:
        payload["json_schema"] = options.json_schema

    return payload


def _build_mock_content(
    user_message: str, json_schema: bool, config: LLMConfig, provider: LLMProvider
) -> str:
    """Generate deterministic mock content."""

    timestamp = datetime.utcnow().isoformat()

    if json_schema:
        mock_body: Dict[str, Any] = {
            "answer": f"模拟回答：收到问题「{user_message[:30] or '（空输入）'}」",
            "meta": {
                "config": config.name,
                "provider": provider.name,
                "timestamp": timestamp,
            },
        }
        return json.dumps(mock_body, ensure_ascii=False)

    return f"（模拟回复）{user_message or '无输入'} —— {timestamp}"


async def send_request(
    config: LLMConfig,
    provider: LLMProvider,
    options: LLMRequestOptions,
    *,
    stream: bool = False,
    preemption_checker=None,
) -> LLMProviderResult:
    """
    Unified mock adapter.

    Args:
        config: LLM configuration
        provider: LLM provider instance
        options: Normalized request options
        stream: Whether streaming was requested (ignored for mock)
        preemption_checker: Optional async callable used to cancel streaming
    """

    payload = _build_payload(config, provider, options)

    # Simulate inference latency
    await asyncio.sleep(0.2)

    if preemption_checker and await preemption_checker():
        logger.info("mock_llm_request_preempted", config_name=config.name)
        return LLMProviderResult(
            content=None,
            model=config.model_name or provider.default_model or "mock-model-v1",
            usage=None,
            finish_reason="preempted",
            raw_response={"mock": True, "payload": payload},
            request_params=payload,
            preempted=True,
        )

    last_user_message = next(
        (msg.get("content", "") for msg in reversed(options.messages) if msg.get("role") == "user"),
        "",
    )
    content = _build_mock_content(last_user_message, bool(options.json_schema), config, provider)

    prompt_tokens = sum(len(msg.get("content", "")) // 4 + 1 for msg in options.messages)
    completion_tokens = len(content) // 4 + 1
    usage = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }

    logger.info(
        "mock_llm_response_generated",
        config_name=config.name,
        provider=provider.name,
    )

    reasoning_content = None
    if (options.thinking_mode or config.thinking_mode) == "enabled":
        reasoning_content = f"Mock reasoning trace for: {last_user_message or 'empty input'}"

    response_identifier = f"mock-{int(datetime.utcnow().timestamp() * 1000)}"

    return LLMProviderResult(
        content=content,
        model=config.model_name or provider.default_model or "mock-model-v1",
        usage=usage,
        finish_reason="stop",
        raw_response={"mock": True, "payload": payload},
        request_params=payload,
        response_id=response_identifier,
        reasoning_content=reasoning_content,
    )
