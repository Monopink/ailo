"""
AI Personality JSON Schema Generator.
Generates JSON Schema from structured configuration.
"""

from typing import Any, Dict


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
