"""
AI response schema utilities.

This module centralizes JSON schema generation so that business layers
can share the same implementation without introducing circular imports.
"""

from typing import Any, Dict, List

from exceptions import AIServiceError
from services.ai.types import InstanceContext
from utils.logging import get_logger

logger = get_logger(__name__)


def generate_json_schema(schema_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate JSON Schema from structured configuration.

    Args:
        schema_config: Configuration containing dimensions and custom_fields

    Returns:
        Complete JSON Schema dict
    """
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "AI Response Schema with Memory Operations",
        "type": "object",
        "required": [
            "should_block",
            "should_reply",
            "attack_detected",
            "should_update_memory",
            "memory_operations",
        ],
        "properties": {},
        "additionalProperties": True,
    }

    # System fields (always included)
    schema["properties"].update(
        {
            "should_block": {"type": "boolean", "description": "Whether to block the message"},
            "should_reply": {"type": "boolean", "description": "Whether AI should reply"},
            "attack_detected": {"type": "boolean", "description": "Whether attack is detected"},
            "followup_messages": {
                "type": "array",
                "description": "Follow-up messages",
                "items": {"type": "string"},
            },
            "memory_operations": {
                "type": "array",
                "description": "顺序执行的记忆操作列表，每条操作会在前一条操作修改后的记忆上执行",
                "items": {
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string",
                            "enum": ["add", "replace", "delete"],
                            "description": "操作类型：增加、替换或删除",
                        },
                        "content": {
                            "type": "string",
                            "description": "新增或替换的内容，仅在 add 和 replace 时必填",
                        },
                        "target_text": {
                            "type": "string",
                            "description": "要匹配的旧文本，仅在 replace 和 delete 时必填",
                        },
                        "insert_position": {
                            "type": "string",
                            "description": "新增内容的插入位置，仅在 add 时有效，可为 'start', 'end', 'after:<text>', 'before:<text>'",
                        },
                    },
                    "required": ["operation"],
                    "additionalProperties": False,
                    "allOf": [
                        {
                            "if": {"properties": {"operation": {"const": "add"}}},
                            "then": {"required": ["content", "insert_position"]},
                        },
                        {
                            "if": {"properties": {"operation": {"const": "replace"}}},
                            "then": {"required": ["target_text", "content"]},
                        },
                        {
                            "if": {"properties": {"operation": {"const": "delete"}}},
                            "then": {"required": ["target_text"]},
                        },
                    ],
                },
            },
            "outgoing_messages": {
                "type": "array",
                "description": "Outgoing messages",
                "items": {"type": "string"},
            },
            "should_update_memory": {"type": "boolean", "description": "Whether to update memory"},
        }
    )

    # Dimensions (score fields)
    dimensions = schema_config.get("dimensions", [])
    if dimensions:
        score_properties = {}
        score_required = []

        for dim in dimensions:
            score_properties[dim["name"]] = {
                "type": "integer",
                "minimum": dim.get("min", 0),
                "maximum": dim.get("max", 1000),
            }
            score_required.append(dim["name"])

        schema["properties"]["score"] = {
            "type": "object",
            "required": score_required,
            "properties": score_properties,
            "additionalProperties": False,
        }
        schema["required"].append("score")

    # Custom fields (including preset fields like internal_thoughts and current_state)
    custom_fields = schema_config.get("custom_fields", [])
    for field in custom_fields:
        field_name = field.get("name")
        if not field_name:
            continue

        schema["properties"][field_name] = {"type": field.get("type", "string")}

        if field.get("description"):
            schema["properties"][field_name]["description"] = field["description"]

        if field.get("required"):
            schema["required"].append(field_name)

    return schema


def build_response_schema(context: InstanceContext) -> Dict[str, Any]:
    """Build JSON schema directly from instance context."""

    try:
        dimensions = context.get("dimensions", [])
        if not dimensions:
            raise AIServiceError(
                ai_service="schema_building",
                reason="dimensions_not_found",
                message=f"Style {context['style']['id']} has no configured dimensions",
            )

        schema = _build_dynamic_response_schema(context["style"], dimensions)

        logger.debug(
            "response_schema_built",
            instance_qiao_id=context["instance_qiao_id"],
            style_id=context["style"]["id"],
            dimensions_count=len(dimensions),
        )

        return schema

    except AIServiceError:
        raise
    except Exception as exc:
        logger.error(
            "response_schema_build_failed",
            error=str(exc),
            instance_qiao_id=context.get("instance_qiao_id"),
        )
        raise AIServiceError(
            ai_service="schema_building",
            reason="unexpected_error",
            message=f"Failed to build response schema: {str(exc)}",
        ) from exc


def _build_dynamic_response_schema(style: Any, dimensions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Build dynamic JSON schema based on AI style and dimensions.
    """
    try:
        style_id = style.get("id") if isinstance(style, dict) else getattr(style, "id", None)

        if not dimensions:
            raise AIServiceError(
                ai_service="schema_building",
                reason="empty_dimensions",
                message=f"Style {style_id} has no active dimensions. "
                f"This indicates a database configuration error.",
            )

        score_properties = {}
        score_required = []

        for dimension in dimensions:
            dimension_name = dimension.get("name")
            if not dimension_name or not isinstance(dimension_name, str):
                raise AIServiceError(
                    ai_service="schema_building",
                    reason="invalid_dimension_name",
                    message=f"Style {style_id} contains invalid dimension name: {dimension_name}. "
                    f"All dimension names must be non-empty strings.",
                )
            score_properties[dimension_name] = {"type": "integer", "minimum": 0, "maximum": 1000}
            score_required.append(dimension_name)

        logger.debug(
            "dynamic_schema_built_successfully",
            style_id=style_id,
            score_names=list(score_properties.keys()),
            score_count=len(score_properties),
        )

        return _get_base_response_schema(score_properties, score_required)

    except AIServiceError:
        raise
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error(
            "dynamic_schema_build_failed",
            error=str(exc),
            style_id=style_id if "style_id" in locals() else getattr(style, "id", "unknown"),
        )
        raise AIServiceError(
            ai_service="schema_building",
            reason="build_failed",
            message=f"Failed to build dynamic schema: {str(exc)}",
        )


def _get_base_response_schema(
    score_properties: Dict[str, Any], score_required: List[str]
) -> Dict[str, Any]:
    """Get base JSON schema structure with dynamic score fields."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "AI Response Schema with Memory Operations",
        "type": "object",
        "properties": {
            "current_state": {
                "type": "string",
                "description": "根据当前时间等信息，推测补充你当前的所处的地点环境、正在做的事情、你的心情",
            },
            "internal_thoughts": {
                "type": "string",
                "description": "回复前的思考（整理你与{USER}的关系，{USER}的身份、意图，回复的原则）",
            },
            "should_block": {"type": "boolean"},
            "should_reply": {"type": "boolean"},
            "attack_detected": {"type": "boolean"},
            "should_update_memory": {"type": "boolean"},
            "memory_operations": {"type": "array"},
            "score": {
                "type": "object",
                "required": score_required,
                "properties": score_properties,
                "additionalProperties": False,
            },
        },
        "required": [
            "current_state",
            "internal_thoughts",
            "should_block",
            "should_reply",
            "attack_detected",
            "should_update_memory",
            "memory_operations",
            "score",
        ],
        "additionalProperties": True,
    }
