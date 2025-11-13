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
    user_message: str, json_schema: Dict[str, Any] | None, config: LLMConfig, provider: LLMProvider
) -> str:
    """Generate deterministic mock content."""

    timestamp = datetime.utcnow().isoformat()

    if json_schema:
        # Generate mock response matching the required schema structure
        schema_props = json_schema.get("properties", {})
        required_fields = json_schema.get("required", [])

        mock_body: Dict[str, Any] = {}

        # Fill in required fields + critical optional fields
        all_fields = set(required_fields)
        # Add critical optional fields that are needed for conversation flow
        all_fields.update(["outgoing_messages", "followup_messages", "internal_thoughts"])

        for field in all_fields:
            field_schema = schema_props.get(field, {})
            field_type = field_schema.get("type")

            if field == "current_state":
                mock_body[field] = f"模拟状态：正在处理消息「{user_message[:20] or '空'}」"
            elif field == "internal_thoughts":
                mock_body[field] = "模拟思考过程"
            elif field == "attack_detected":
                mock_body[field] = False
            elif field == "should_reply":
                mock_body[field] = True
            elif field == "outgoing_messages":
                mock_body[field] = [f"模拟回复：{user_message[:30] or '（空输入）'}"]
            elif field == "score":
                mock_body[field] = {"friendship": 500, "romance": 500}
            elif field == "followup_messages":
                mock_body[field] = ["模拟追加消息1", "模拟追加消息2"]
            elif field == "should_block":
                mock_body[field] = False
            elif field == "should_update_memory":
                mock_body[field] = True
            elif field == "memory_operations":
                mock_body[field] = [
                    {"operation": "add", "content": f"用户说：{user_message[:20]}", "insert_position": "end"}
                ]
            elif field_type == "string":
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

    # Extract last user message, handling both string and list content formats
    last_user_message = ""
    for msg in reversed(options.messages):
        if msg.get("role") == "user":
            content_value = msg.get("content", "")
            if isinstance(content_value, list):
                # Extract text from content blocks (e.g., [{"type": "input_text", "text": "..."}])
                text_parts = []
                for block in content_value:
                    if isinstance(block, dict) and "text" in block:
                        text_parts.append(block["text"])
                last_user_message = " ".join(text_parts)
            else:
                last_user_message = str(content_value)
            break

    content = _build_mock_content(last_user_message, options.json_schema, config, provider)

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
        content_preview=content[:100] if isinstance(content, str) else str(content)[:100],
        has_json_schema=options.json_schema is not None,
    )

    reasoning_content = None
    if (options.thinking_mode or config.thinking_mode) == "enabled":
        reasoning_content = f"""[模拟思考过程]
1. 分析用户消息：{last_user_message[:50] or '空输入'}
2. 判断用户意图：正常对话
3. 确定回复策略：友好回应
4. 生成回复内容"""

    response_identifier = f"mock-{int(datetime.utcnow().timestamp() * 1000)}"

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
