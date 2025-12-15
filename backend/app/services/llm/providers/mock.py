"""
Mock LLM provider implementation for testing.

This adapter mimics the Responses API behavior so that upstream logic can
be exercised without calling a real provider.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from app.models.llm import LLMConfig, LLMProvider
from app.services.llm.converters import ResponsesFormatConverter
from app.services.llm.types import LLMProviderResult, LLMRequestOptions
from app.utils.logging import get_logger

logger = get_logger(__name__)


_converter = ResponsesFormatConverter()


def _build_current_state(user_message: str) -> str:
    snippet = user_message[:20] or "empty input"
    return f'Currently chatting while processing "{snippet}".'


def _build_internal_thoughts(_: str) -> str:
    return "Plan a friendly reply that matches the relationship and policies."


def _build_outgoing_messages(user_message: str) -> list[str]:
    snippet = user_message[:30] or "no input"
    return [f"Mock reply: {snippet}"]


def _build_followups(user_message: str) -> list[str]:
    base = user_message[:15] or "next topic"
    return [f"Mock follow-up: {base}?", "Mock follow-up: anything else?"]


def _build_memory_operations_entry(user_message: str) -> dict[str, Any]:
    return {
        "remove": [],
        "update": [],
        "refresh": [],
        "add": [
            {
                "memory_type": "recent",
                "content": f"User said: {user_message[:20]}",
                "importance": 5,
            }
        ],
    }


def _build_score_field(_: str) -> dict[str, int]:
    return {"friendship": 500, "romance": 500}


_STATIC_FIELD_VALUES: dict[str, Any] = {
    "attack_detected": False,
    "should_reply": True,
    "should_block": False,
    "should_update_memory": True,
}

_FIELD_BUILDERS: dict[str, Callable[[str], Any]] = {
    "current_state": _build_current_state,
    "internal_thoughts": _build_internal_thoughts,
    "outgoing_messages": _build_outgoing_messages,
    "followup_messages": _build_followups,
    "memory_operations": _build_memory_operations_entry,
    "score": _build_score_field,
}


def _build_payload(
    config: LLMConfig,
    provider: LLMProvider,
    options: LLMRequestOptions,
    provider_messages: list[dict[str, Any]],
) -> dict[str, Any]:
    """Create a payload snapshot to simplify debugging."""

    payload: dict[str, Any] = {
        "model": options.model or config.model_name or provider.default_model or "mock-model-v1",
        "messages": options.messages,
        "input": provider_messages,
        "temperature": (
            options.temperature
            if options.temperature is not None
            else (float(config.temperature) if config.temperature is not None else 0.7)
        ),
        "max_tokens": options.max_tokens
        if options.max_tokens is not None
        else config.max_tokens or 1024,
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
    user_message: str, json_schema: dict[str, Any] | None, config: LLMConfig, provider: LLMProvider
) -> str:
    """Generate deterministic mock content."""

    timestamp = datetime.now(UTC).isoformat()

    if json_schema:
        # Generate mock response matching the required schema structure
        schema_props = json_schema.get("properties", {})
        required_fields = json_schema.get("required", [])

        mock_body: dict[str, Any] = {}

        # Fill in required fields + critical optional fields
        all_fields = set(required_fields)
        # Add critical optional fields that are needed for conversation flow
        all_fields.update(["outgoing_messages", "followup_messages", "internal_thoughts"])

        for field in all_fields:
            field_schema = schema_props.get(field, {})
            field_type = field_schema.get("type")

            if field in _STATIC_FIELD_VALUES:
                mock_body[field] = _STATIC_FIELD_VALUES[field]
                continue

            builder = _FIELD_BUILDERS.get(field)
            if builder:
                mock_body[field] = builder(user_message)
                continue

            if field_type == "string":
                mock_body[field] = f"mock_{field}"
            elif field_type == "boolean":
                mock_body[field] = False
            elif field_type == "integer":
                mock_body[field] = 0
            elif field_type == "array":
                mock_body[field] = []
            elif field_type == "object":
                mock_body[field] = {}

        # Add meta information
        mock_body["_meta"] = {
            "config": config.name,
            "provider": provider.name,
            "timestamp": timestamp,
        }

        return json.dumps(mock_body, ensure_ascii=False)

    return f"(Mock reply) {user_message or 'no input'} — {timestamp}"


async def send_request(
    config: LLMConfig,
    provider: LLMProvider,
    options: LLMRequestOptions,
    *,
    stream: bool = False,
    preemption_checker: Callable[[], Awaitable[bool]] | None = None,
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

    _ = stream  # maintained for API parity
    provider_messages = _converter.convert_to_provider_format(options.messages)
    payload = _build_payload(config, provider, options, provider_messages)

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

    # Extract last user message, handling both string and list content formats
    last_user_message = _extract_last_user_message(provider_messages)

    content = _build_mock_content(last_user_message, options.json_schema, config, provider)

    prompt_tokens = _estimate_tokens(provider_messages)
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
        content_preview=content[:100] if isinstance(content, str) else str(content)[:100],
        has_json_schema=options.json_schema is not None,
    )

    reasoning_content = None
    if (options.thinking_mode or config.thinking_mode) == "enabled":
        reasoning_content = (
            "[Mock reasoning]\n"
            f"1. Analyze user message: {last_user_message[:50] or 'empty input'}\n"
            "2. Determine intent: casual chat\n"
            "3. Choose reply strategy: friendly tone\n"
            "4. Produce final response"
        )

    response_identifier = f"mock-{int(datetime.now(UTC).timestamp() * 1000)}"

    # Build Doubao Responses API compatible raw_response
    content_blocks = [{"type": "output_text", "text": content}]
    if reasoning_content:
        content_blocks.insert(0, {"type": "thinking", "thinking": reasoning_content})

    raw_response = {
        "id": response_identifier,
        "model": config.model_name or provider.default_model or "mock-model-v1",
        "output": [{"type": "message", "role": "assistant", "content": content_blocks}],
        "usage": usage,
        "finish_reason": "stop",
        "_mock": True,
    }

    return LLMProviderResult(
        content=content,
        model=config.model_name or provider.default_model or "mock-model-v1",
        usage=usage,
        finish_reason="stop",
        raw_response=raw_response,
        request_params=payload,
        response_id=response_identifier,
        reasoning_content=reasoning_content,
    )


def _extract_last_user_message(provider_messages: list[dict[str, Any]]) -> str:
    for msg in reversed(provider_messages):
        if msg.get("role") != "user":
            continue
        content_blocks = msg.get("content")
        if isinstance(content_blocks, list):
            text_parts: list[str] = []
            for block in content_blocks:
                if isinstance(block, dict) and block.get("type") in ("input_text", "text"):
                    value = block.get("text") or block.get("input_text")
                    if isinstance(value, str):
                        text_parts.append(value)
            if text_parts:
                return " ".join(text_parts)
        fallback = msg.get("text")
        if isinstance(fallback, str) and fallback:
            return fallback
    return ""


def _estimate_tokens(provider_messages: list[dict[str, Any]]) -> int:
    total = 0
    for msg in provider_messages:
        blocks = msg.get("content")
        if isinstance(blocks, list):
            for block in blocks:
                text = block.get("text") if isinstance(block, dict) else None
                if isinstance(text, str):
                    total += max(len(text) // 4 + 1, 1)
        elif isinstance(msg.get("text"), str):
            total += max(len(msg["text"]) // 4 + 1, 1)
    return total or 1
