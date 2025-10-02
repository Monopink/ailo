"""
Mock LLM provider implementation for testing.

This module provides a mock implementation for testing AI functionality
without making actual API calls.
"""

import json
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime

from models.llm import LLMConfig, LLMProvider
from utils.logging import get_logger

logger = get_logger(__name__)


def _build_mock_payload(
    config: LLMConfig,
    provider: LLMProvider,
    messages: List[Dict[str, str]],
    json_schema: Optional[Dict[str, Any]],
    temperature: Optional[float],
    max_tokens: Optional[int],
    enable_thinking: Optional[bool],
) -> Dict[str, Any]:
    """
    Build request payload matching Doubao API format for consistency.

    This ensures mock requests have the same structure as real Doubao requests,
    making it easier to test and debug.
    """
    # Use mock model name or default
    model = config.model_name or provider.default_model or "mock-model-v1"

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

    # Add structured output support (matching Doubao format)
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

    # Add thinking mode support (matching Doubao format)
    if provider.supports_thinking:
        thinking_enabled = enable_thinking if enable_thinking is not None else config.enable_thinking
        payload["thinking"] = {"type": "enabled" if thinking_enabled else "disabled"}

    return payload


async def chat_completion(
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
    Mock chat completion for testing purposes.

    Args:
        config: LLM configuration
        provider: LLM provider information
        messages: List of message objects with 'role' and 'content'
        json_schema: Optional JSON schema for structured output
        temperature: Override temperature setting
        max_tokens: Override max tokens setting
        enable_thinking: Override thinking mode setting
        timeout: Optional timeout override (not used in mock)

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
    """
    # Build complete request payload (matching Doubao API format)
    payload = _build_mock_payload(
        config, provider, messages, json_schema, temperature, max_tokens, enable_thinking
    )

    # Simulate processing delay
    await asyncio.sleep(0.5)

    # Get the last user message
    user_message = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            user_message = msg.get("content", "")
            break

    # Generate mock response based on JSON schema or default
    if json_schema:
        response_content = _generate_structured_response(json_schema, user_message)
        # Convert to JSON string for structured output
        content = json.dumps(response_content, ensure_ascii=False)
    else:
        content = _generate_text_response(user_message)

    # Mock usage statistics
    usage = {
        "prompt_tokens": sum(len(msg.get("content", "").split()) for msg in messages),
        "completion_tokens": len(str(content).split()),
        "total_tokens": 0,
    }
    usage["total_tokens"] = usage["prompt_tokens"] + usage["completion_tokens"]

    return {
        "content": content,
        "model": payload["model"],
        "usage": usage,
        "finish_reason": "stop",
    }


# Keep old function name for backward compatibility
async def mock_chat_completion(
    config: LLMConfig,
    provider: LLMProvider,
    messages: List[Dict[str, str]],
    json_schema: Optional[Dict[str, Any]] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    enable_thinking: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Legacy mock chat completion function.

    This function is kept for backward compatibility.
    New code should use chat_completion() instead.
    """
    try:
        result = await chat_completion(
            config, provider, messages, json_schema, temperature, max_tokens, enable_thinking
        )

        return {
            "success": True,
            "response": result["content"],
            "raw_content": result["content"],
            "usage": result["usage"],
            "model": result["model"],
            "finish_reason": result["finish_reason"],
            "request_payload": _build_mock_payload(
                config, provider, messages, json_schema, temperature, max_tokens, enable_thinking
            ),
        }

    except Exception as e:
        logger.error("mock_chat_completion_error", error=str(e))
        return {
            "success": False,
            "error": str(e),
            "response": None,
            "usage": None,
            "request_payload": None,
        }


def _generate_structured_response(json_schema: Dict[str, Any], user_message: str) -> Dict[str, Any]:
    """Generate a structured response based on JSON schema."""
    try:
        # Basic schema-based response generation
        response = {}
        properties = json_schema.get("properties", {})

        for field_name, field_schema in properties.items():
            field_type = field_schema.get("type", "string")

            if field_name == "current_state":
                response[field_name] = "我现在在房间里，心情很好，准备和你聊天。"
            elif field_name == "internal_thoughts":
                response[field_name] = f"用户说了：{user_message[:50]}...，我需要友好地回应。"
            elif field_name == "attack_detected":
                response[field_name] = False
            elif field_name == "should_reply":
                response[field_name] = True
            elif field_name == "outgoing_messages":
                response[field_name] = [
                    f"嗯嗯，听到了～你说：{user_message[:30]}{'...' if len(user_message) > 30 else ''}",
                    "有什么想聊的吗？我在呢！",
                ]
            elif field_name == "score":
                # Generate mock scores based on schema
                score_obj = {}
                score_properties = field_schema.get("properties", {})
                for score_field in score_properties.keys():
                    score_obj[score_field] = 500  # Default middle value
                response[field_name] = score_obj
            elif field_name == "followup_messages":
                response[field_name] = ["你今天过得怎么样？"]
            elif field_name == "should_block":
                response[field_name] = False
            elif field_name == "should_update_memory":
                response[field_name] = True
            elif field_name == "memory_operations":
                response[field_name] = [
                    {
                        "operation": "add",
                        "insert_position": "end",
                        "content": f"用户在{datetime.now().strftime('%Y-%m-%d %H:%M')}说了：{user_message[:50]}",
                    }
                ]
            elif field_type == "string":
                response[field_name] = f"Mock {field_name} value"
            elif field_type == "integer":
                response[field_name] = 42
            elif field_type == "boolean":
                response[field_name] = True
            elif field_type == "array":
                response[field_name] = ["mock_item_1", "mock_item_2"]
            elif field_type == "object":
                response[field_name] = {"mock_key": "mock_value"}

        return response

    except Exception as e:
        logger.error("mock_structured_response_error", error=str(e))
        return {
            "current_state": "Mock state",
            "internal_thoughts": "Mock thoughts",
            "attack_detected": False,
            "should_reply": True,
            "outgoing_messages": ["这是一个模拟回复"],
            "score": {"default": 500},
            "should_update_memory": False,
            "memory_operations": [],
        }


def _generate_text_response(user_message: str) -> str:
    """Generate a simple text response."""
    if not user_message:
        return "你好！我是AI助手，有什么可以帮助你的吗？"

    # Simple response patterns
    if "你好" in user_message or "hello" in user_message.lower():
        return "你好！很高兴见到你！"
    elif "怎么样" in user_message or "如何" in user_message:
        return "我觉得很不错！你呢？"
    elif "谢谢" in user_message or "thank" in user_message.lower():
        return "不客气！很高兴能帮到你。"
    elif "再见" in user_message or "bye" in user_message.lower():
        return "再见！期待下次聊天！"
    else:
        return f"我收到了你的消息：「{user_message[:50]}{'...' if len(user_message) > 50 else ''}」。这是一个模拟回复，实际的AI会根据具体情况给出更合适的回应。"
