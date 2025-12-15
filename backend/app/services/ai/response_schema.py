"""
AI response schema utilities.

This module centralizes JSON schema generation so that business layers
can share the same implementation without introducing circular imports.
"""

from typing import Any

from app.exceptions import AIServiceError
from app.services.ai.types import DimensionSpec, InstanceContext
from app.utils.logging import get_logger

logger = get_logger(__name__)


def _build_memory_operations_schema() -> dict[str, Any]:
    """Return the common schema definition for memory operations."""

    return {
        "type": "object",
        "description": "Memory operations object processed in remove→update→refresh→add order",
        "properties": {
            "remove": {
                "type": "array",
                "description": "List of memory contents to delete (exact content match)",
                "items": {"type": "string"},
            },
            "update": {
                "type": "array",
                "description": "Update memory entries with new content/importance",
                "items": {
                    "type": "object",
                    "properties": {
                        "old_content": {"type": "string"},
                        "new_content": {"type": "string"},
                        "new_importance": {"type": "integer", "minimum": 1, "maximum": 10},
                    },
                    "required": ["old_content", "new_content"],
                    "additionalProperties": False,
                },
            },
            "refresh": {
                "type": "array",
                "description": "Memories that should be refreshed/extended",
                "items": {"type": "string"},
            },
            "add": {
                "type": "array",
                "description": "New memories to insert",
                "items": {
                    "type": "object",
                    "properties": {
                        "memory_type": {"type": "string", "enum": ["core", "recent"]},
                        "content": {"type": "string"},
                        "importance": {"type": "integer", "minimum": 1, "maximum": 10},
                    },
                    "required": ["memory_type", "content", "importance"],
                    "additionalProperties": False,
                },
            },
        },
        "additionalProperties": False,
    }


def generate_json_schema(schema_config: dict[str, Any]) -> dict[str, Any]:
    """
    Generate JSON Schema from structured configuration.

    Args:
        schema_config: Configuration containing dimensions and custom_fields

    Returns:
        Complete JSON Schema dict
    """
    schema: dict[str, Any] = {
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
    properties: dict[str, Any] = schema["properties"]
    required_fields: list[str] = schema["required"]

    # System fields (always included)
    properties.update(
        {
            "should_block": {"type": "boolean", "description": "Whether to block the message"},
            "should_reply": {"type": "boolean", "description": "Whether AI should reply"},
            "attack_detected": {"type": "boolean", "description": "Whether attack is detected"},
            "followup_messages": {
                "type": "array",
                "description": "Follow-up messages",
                "items": {"type": "string"},
            },
            "memory_operations": _build_memory_operations_schema(),
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

        properties["score"] = {
            "type": "object",
            "required": score_required,
            "properties": score_properties,
            "additionalProperties": False,
        }
        required_fields.append("score")

    # Custom fields (including preset fields like internal_thoughts and current_state)
    custom_fields = schema_config.get("custom_fields", [])
    for field in custom_fields:
        field_name = field.get("name")
        if not field_name:
            continue

        properties[field_name] = {"type": field.get("type", "string")}

        if field.get("description"):
            properties[field_name]["description"] = field["description"]

        if field.get("required"):
            required_fields.append(field_name)

    return schema


def build_response_schema(context: InstanceContext) -> dict[str, Any]:
    """Build JSON schema directly from instance context."""

    dimensions: list[DimensionSpec] = context.get("dimensions", [])
    if not dimensions:
        raise AIServiceError(
            ai_service="schema_building",
            reason="dimensions_not_found",
            message=f"Style {context['style']['id']} has no configured dimensions",
        )

    try:
        schema = _build_dynamic_response_schema(context["style"], dimensions)

        logger.debug(
            "response_schema_built",
            instance_qiao_id=context["instance_qiao_id"],
            style_id=context["style"]["id"],
            dimensions_count=len(dimensions),
        )

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
            message=f"Failed to build response schema: {exc!s}",
        ) from exc
    else:
        return schema


def _build_dynamic_response_schema(style: Any, dimensions: list[DimensionSpec]) -> dict[str, Any]:
    """
    Build dynamic JSON schema based on AI style and dimensions.
    """
    style_id = style.get("id") if isinstance(style, dict) else getattr(style, "id", None)

    try:
        score_properties, score_required = _prepare_score_fields(style_id, dimensions)
    except AIServiceError:
        raise
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error(
            "dynamic_schema_build_failed",
            error=str(exc),
            style_id=style_id if style_id is not None else getattr(style, "id", "unknown"),
        )
        raise AIServiceError(
            ai_service="schema_building",
            reason="build_failed",
            message=f"Failed to build dynamic schema: {exc!s}",
        ) from exc

    logger.debug(
        "dynamic_schema_built_successfully",
        style_id=style_id,
        score_names=list(score_properties.keys()),
        score_count=len(score_properties),
    )

    return _get_base_response_schema(score_properties, score_required)


def _prepare_score_fields(
    style_id: Any, dimensions: list[DimensionSpec]
) -> tuple[dict[str, Any], list[str]]:
    """Validate dimensions and build score schema fragments."""

    if not dimensions:
        raise AIServiceError(
            ai_service="schema_building",
            reason="empty_dimensions",
            message=f"Style {style_id} has no active dimensions. "
            "This indicates a database configuration error.",
        )

    score_properties: dict[str, Any] = {}
    score_required: list[str] = []

    for dimension in dimensions:
        dimension_name = dimension.get("name")
        if not dimension_name or not isinstance(dimension_name, str):
            raise AIServiceError(
                ai_service="schema_building",
                reason="invalid_dimension_name",
                message=f"Style {style_id} contains invalid dimension name: {dimension_name}. "
                "All dimension names must be non-empty strings.",
            )
        score_properties[dimension_name] = {"type": "integer", "minimum": 0, "maximum": 1000}
        score_required.append(dimension_name)

    return score_properties, score_required


def _get_base_response_schema(
    score_properties: dict[str, Any], score_required: list[str]
) -> dict[str, Any]:
    """Get base JSON schema structure with dynamic score fields."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "AI Response Schema with Memory Operations",
        "type": "object",
        "properties": {
            "current_state": {
                "type": "string",
                "description": (
                    "Summarize your current environment, activity, and mood based on time/context."
                ),
            },
            "internal_thoughts": {
                "type": "string",
                "description": (
                    "Internal reasoning before replying: relationship with {USER}, user intent, and"
                    " response principles."
                ),
            },
            "should_block": {"type": "boolean"},
            "should_reply": {"type": "boolean"},
            "attack_detected": {"type": "boolean"},
            "followup_messages": {
                "type": "array",
                "items": {"type": "string"},
            },
            "outgoing_messages": {
                "type": "array",
                "items": {"type": "string"},
            },
            "should_update_memory": {"type": "boolean"},
            "memory_operations": _build_memory_operations_schema(),
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
