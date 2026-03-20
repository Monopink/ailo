"""Admin AI Personality API endpoints.
Handles personality management including prompts, schemas, and placeholders.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.crud.ai import ai_personality_placeholder as placeholder_crud
from app.models.ai.instance import AIInstance
from app.models.ai.personality import AIPersonality, AIPersonalityPlaceholder
from app.models.ai.template import AITemplate
from app.services.ai.response_schema import generate_json_schema
from app.utils.logging import get_logger

logger = get_logger(__name__)

personality_router = APIRouter()

_ALLOWED_JSON_TYPES = {"string", "integer", "number", "boolean", "object", "array"}
_RESERVED_FIELD_NAMES = {
    "should_block",
    "should_reply",
    "attack_detected",
    "should_update_memory",
    "memory_operations",
    "followup_messages",
    "outgoing_messages",
    "score",
}


def _extract_score_dimension_names(schema: object, *, field_name: str) -> set[str]:
    """Extract score dimension names from JSON schema with strict structure checks."""
    if not isinstance(schema, dict):
        raise HTTPException(status_code=400, detail=f"{field_name} must be an object")

    properties_raw = schema.get("properties")
    if not isinstance(properties_raw, dict):
        raise HTTPException(status_code=400, detail=f"{field_name}.properties is required")

    score_raw = properties_raw.get("score")
    if not isinstance(score_raw, dict):
        raise HTTPException(status_code=400, detail=f"{field_name}.properties.score is required")

    score_properties_raw = score_raw.get("properties")
    if not isinstance(score_properties_raw, dict) or not score_properties_raw:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name}.properties.score.properties is required",
        )

    names: set[str] = set()
    for raw_name in score_properties_raw:
        if not isinstance(raw_name, str) or not raw_name.strip():
            raise HTTPException(
                status_code=400,
                detail=f"{field_name}.properties.score.properties has invalid dimension name",
            )
        names.add(raw_name.strip())
    return names


async def _personality_has_references(db: AsyncSession, personality_id: int) -> bool:
    """Return True if any instance or template references this personality."""
    instance_ref = await db.execute(
        select(AIInstance.id).where(AIInstance.personality_id == personality_id).limit(1)
    )
    if instance_ref.scalar_one_or_none() is not None:
        return True

    template_ref = await db.execute(
        select(AITemplate.id).where(AITemplate.personality_id == personality_id).limit(1)
    )
    return template_ref.scalar_one_or_none() is not None


def _parse_int_id(value: object, *, field_name: str) -> int:
    """Parse identifier-like values into int with strict error handling."""
    if isinstance(value, bool) or value is None:
        raise HTTPException(status_code=400, detail=f"{field_name} must be an integer")
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = int(value)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"{field_name} must be an integer") from exc
    else:
        raise HTTPException(status_code=400, detail=f"{field_name} must be an integer")
    if parsed <= 0:
        raise HTTPException(status_code=400, detail=f"{field_name} must be a positive integer")
    return parsed


def _validate_schema_config(schema_config: object) -> dict[str, Any]:
    """Validate and normalize schema_config payload."""
    if not isinstance(schema_config, dict):
        raise HTTPException(status_code=400, detail="schema_config is required")

    raw_dimensions = schema_config.get("dimensions")
    if not isinstance(raw_dimensions, list) or not raw_dimensions:
        raise HTTPException(status_code=400, detail="dimensions are required")

    dimension_names: set[str] = set()
    dimensions: list[dict[str, Any]] = []
    for index, raw_dim in enumerate(raw_dimensions):
        if not isinstance(raw_dim, dict):
            raise HTTPException(status_code=400, detail=f"dimensions[{index}] must be an object")

        raw_name = raw_dim.get("name")
        if not isinstance(raw_name, str) or not raw_name.strip():
            raise HTTPException(status_code=400, detail=f"dimensions[{index}].name is required")
        dim_name = raw_name.strip()
        if dim_name in dimension_names:
            raise HTTPException(
                status_code=400,
                detail=f"duplicate dimension name: {dim_name}",
            )
        dimension_names.add(dim_name)

        if "min" not in raw_dim or "max" not in raw_dim:
            raise HTTPException(
                status_code=400,
                detail=f"dimensions[{index}] must include min and max",
            )
        raw_min = raw_dim.get("min")
        raw_max = raw_dim.get("max")
        if isinstance(raw_min, bool) or not isinstance(raw_min, int | float):
            raise HTTPException(status_code=400, detail=f"dimensions[{index}].min must be numeric")
        if isinstance(raw_max, bool) or not isinstance(raw_max, int | float):
            raise HTTPException(status_code=400, detail=f"dimensions[{index}].max must be numeric")
        if float(raw_min) >= float(raw_max):
            raise HTTPException(
                status_code=400,
                detail=f"dimensions[{index}] requires min < max",
            )

        raw_description = raw_dim.get("description", "")
        if raw_description is None:
            description = ""
        elif isinstance(raw_description, str):
            description = raw_description.strip()
        else:
            raise HTTPException(
                status_code=400,
                detail=f"dimensions[{index}].description must be a string",
            )

        dimensions.append(
            {
                "name": dim_name,
                "min": float(raw_min),
                "max": float(raw_max),
                "description": description,
            }
        )

    raw_custom_fields = schema_config.get("custom_fields", [])
    if raw_custom_fields is None:
        raw_custom_fields = []
    if not isinstance(raw_custom_fields, list):
        raise HTTPException(status_code=400, detail="custom_fields must be a list")

    custom_names: set[str] = set()
    custom_fields: list[dict[str, Any]] = []
    for index, raw_field in enumerate(raw_custom_fields):
        if not isinstance(raw_field, dict):
            raise HTTPException(status_code=400, detail=f"custom_fields[{index}] must be an object")

        raw_name = raw_field.get("name")
        if not isinstance(raw_name, str) or not raw_name.strip():
            raise HTTPException(status_code=400, detail=f"custom_fields[{index}].name is required")
        field_name = raw_name.strip()
        if field_name in custom_names:
            raise HTTPException(status_code=400, detail=f"duplicate custom field: {field_name}")
        if field_name in _RESERVED_FIELD_NAMES:
            raise HTTPException(
                status_code=400,
                detail=f"custom field conflicts with reserved field: {field_name}",
            )
        custom_names.add(field_name)

        raw_type = raw_field.get("type", "string")
        if not isinstance(raw_type, str) or raw_type not in _ALLOWED_JSON_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"custom_fields[{index}].type is invalid",
            )

        raw_description = raw_field.get("description", "")
        if raw_description is None:
            description = ""
        elif isinstance(raw_description, str):
            description = raw_description.strip()
        else:
            raise HTTPException(
                status_code=400,
                detail=f"custom_fields[{index}].description must be a string",
            )

        raw_required = raw_field.get("required", False)
        if not isinstance(raw_required, bool):
            raise HTTPException(
                status_code=400,
                detail=f"custom_fields[{index}].required must be a boolean",
            )

        custom_fields.append(
            {
                "name": field_name,
                "type": raw_type,
                "description": description,
                "required": raw_required,
            }
        )

    return {
        "dimensions": dimensions,
        "custom_fields": custom_fields,
    }


def _validate_placeholders(raw_placeholders: object) -> list[dict[str, Any]]:
    """Validate and normalize placeholders payload."""
    if raw_placeholders is None:
        return []
    if not isinstance(raw_placeholders, list):
        raise HTTPException(status_code=400, detail="placeholders must be a list")

    normalized: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    seen_keys: set[str] = set()
    for index, raw_placeholder in enumerate(raw_placeholders):
        if not isinstance(raw_placeholder, dict):
            raise HTTPException(status_code=400, detail=f"placeholders[{index}] must be an object")

        placeholder_id: int | None = None
        if raw_placeholder.get("id") is not None:
            placeholder_id = _parse_int_id(
                raw_placeholder.get("id"), field_name=f"placeholders[{index}].id"
            )
            if placeholder_id in seen_ids:
                raise HTTPException(
                    status_code=400,
                    detail=f"duplicate placeholder id in payload: {placeholder_id}",
                )
            seen_ids.add(placeholder_id)

        raw_key = raw_placeholder.get("placeholder_key")
        if not isinstance(raw_key, str) or not raw_key.strip():
            raise HTTPException(
                status_code=400,
                detail=f"placeholders[{index}].placeholder_key is required",
            )
        placeholder_key = raw_key.strip()
        if placeholder_key in seen_keys:
            raise HTTPException(
                status_code=400,
                detail=f"duplicate placeholder key in payload: {placeholder_key}",
            )
        seen_keys.add(placeholder_key)

        raw_display_name = raw_placeholder.get("display_name", "")
        if raw_display_name is None:
            display_name = ""
        elif isinstance(raw_display_name, str):
            display_name = raw_display_name.strip()
        else:
            raise HTTPException(
                status_code=400,
                detail=f"placeholders[{index}].display_name must be a string",
            )

        raw_description = raw_placeholder.get("description", "")
        if raw_description is None:
            description = ""
        elif isinstance(raw_description, str):
            description = raw_description.strip()
        else:
            raise HTTPException(
                status_code=400,
                detail=f"placeholders[{index}].description must be a string",
            )

        raw_example_value = raw_placeholder.get("example_value", "")
        if raw_example_value is None:
            example_value = ""
        elif isinstance(raw_example_value, str):
            example_value = raw_example_value.strip()
        else:
            raise HTTPException(
                status_code=400,
                detail=f"placeholders[{index}].example_value must be a string",
            )

        raw_is_required = raw_placeholder.get("is_required", False)
        if not isinstance(raw_is_required, bool):
            raise HTTPException(
                status_code=400,
                detail=f"placeholders[{index}].is_required must be a boolean",
            )

        normalized.append(
            {
                "id": placeholder_id,
                "placeholder_key": placeholder_key,
                "display_name": display_name,
                "description": description,
                "example_value": example_value,
                "is_required": int(raw_is_required),
            }
        )

    return normalized


def _validate_deleted_placeholder_ids(raw_deleted_ids: object) -> list[int]:
    """Validate deleted placeholder id list."""
    if raw_deleted_ids is None:
        return []
    if not isinstance(raw_deleted_ids, list):
        raise HTTPException(status_code=400, detail="deleted_placeholder_ids must be a list")

    deleted_ids: list[int] = []
    seen: set[int] = set()
    for index, raw_id in enumerate(raw_deleted_ids):
        parsed = _parse_int_id(raw_id, field_name=f"deleted_placeholder_ids[{index}]")
        if parsed in seen:
            raise HTTPException(status_code=400, detail=f"duplicate deleted id: {parsed}")
        seen.add(parsed)
        deleted_ids.append(parsed)
    return deleted_ids


@personality_router.get("/ai-personality/{personality_id}/placeholders")
async def get_personality_placeholders(
    personality_id: int, db: AsyncSession = Depends(get_db)
) -> list[dict[str, Any]]:
    """Get placeholders for a personality."""
    placeholders = await placeholder_crud.get_placeholders_by_personality(
        db, personality_id=personality_id
    )
    return [
        {
            "id": p.id,
            "placeholder_key": p.placeholder_key,
            "display_name": p.display_name,
            "description": p.description,
            "example_value": p.example_value,
            "is_required": bool(p.is_required),
        }
        for p in placeholders
    ]


@personality_router.post("/ai-personality/{personality_id}/save")
async def save_personality_all(
    personality_id: int, data: dict[str, Any], db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Save personality prompt/schema/placeholders in one atomic transaction."""
    result = await db.execute(select(AIPersonality).where(AIPersonality.id == personality_id))
    personality = result.scalar_one_or_none()
    if not personality:
        raise HTTPException(status_code=404, detail="Personality not found")

    raw_prompt = data.get("prompt", "")
    if not isinstance(raw_prompt, str):
        raise HTTPException(status_code=400, detail="prompt must be a string")
    prompt = raw_prompt.strip()
    if prompt == "":
        raise HTTPException(status_code=400, detail="prompt cannot be empty")

    schema_config = _validate_schema_config(data.get("schema_config"))
    try:
        json_schema = generate_json_schema(schema_config)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"invalid schema_config: {exc!s}") from exc

    personality_has_references = await _personality_has_references(db, personality_id)
    if personality_has_references:
        existing_dimension_names = _extract_score_dimension_names(
            personality.json_schema,
            field_name="current personality json_schema",
        )
        requested_dimension_names = _extract_score_dimension_names(
            json_schema,
            field_name="generated personality json_schema",
        )
        if existing_dimension_names != requested_dimension_names:
            raise HTTPException(
                status_code=400,
                detail=(
                    "cannot change personality score dimension set because this personality "
                    "is referenced by instances or templates"
                ),
            )

    placeholders = _validate_placeholders(data.get("placeholders", []))
    deleted_placeholder_ids = _validate_deleted_placeholder_ids(
        data.get("deleted_placeholder_ids", [])
    )

    updated = 0
    created = 0
    deleted = 0

    all_target_ids: set[int] = set(deleted_placeholder_ids)
    update_placeholder_ids: set[int] = set()
    for placeholder in placeholders:
        if placeholder["id"] is not None:
            placeholder_id = int(placeholder["id"])
            update_placeholder_ids.add(placeholder_id)
            all_target_ids.add(placeholder_id)

    duplicated_update_and_delete = sorted(
        update_placeholder_ids.intersection(deleted_placeholder_ids)
    )
    if duplicated_update_and_delete:
        raise HTTPException(
            status_code=400,
            detail=(
                f"placeholder id cannot be both updated and deleted: {duplicated_update_and_delete}"
            ),
        )

    existing_placeholders_by_id: dict[int, AIPersonalityPlaceholder] = {}
    if all_target_ids:
        existing_result = await db.execute(
            select(AIPersonalityPlaceholder).where(AIPersonalityPlaceholder.id.in_(all_target_ids))
        )
        existing_placeholders_by_id = {row.id: row for row in existing_result.scalars().all()}

    try:
        personality.prompt = prompt
        personality.json_schema = json_schema
        db.add(personality)

        for placeholder_data in placeholders:
            placeholder_id = placeholder_data["id"]

            if placeholder_id is not None:
                existing_placeholder = existing_placeholders_by_id.get(placeholder_id)
                if existing_placeholder is None:
                    raise HTTPException(
                        status_code=400,
                        detail=f"placeholder not found: {placeholder_id}",
                    )
                if existing_placeholder.personality_id != personality_id:
                    raise HTTPException(
                        status_code=400,
                        detail=f"placeholder does not belong to personality: {placeholder_id}",
                    )
                existing_placeholder.placeholder_key = placeholder_data["placeholder_key"]
                existing_placeholder.display_name = placeholder_data["display_name"]
                existing_placeholder.description = placeholder_data["description"]
                existing_placeholder.example_value = placeholder_data["example_value"]
                existing_placeholder.is_required = placeholder_data["is_required"]
                db.add(existing_placeholder)
                updated += 1
            else:
                new_placeholder = AIPersonalityPlaceholder(
                    personality_id=personality_id,
                    placeholder_key=placeholder_data["placeholder_key"],
                    display_name=placeholder_data["display_name"],
                    description=placeholder_data["description"],
                    example_value=placeholder_data["example_value"],
                    is_required=placeholder_data["is_required"],
                )
                db.add(new_placeholder)
                created += 1

        for placeholder_id in deleted_placeholder_ids:
            existing_placeholder = existing_placeholders_by_id.get(placeholder_id)
            if existing_placeholder is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"placeholder not found: {placeholder_id}",
                )
            if existing_placeholder.personality_id != personality_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"placeholder does not belong to personality: {placeholder_id}",
                )
            await db.delete(existing_placeholder)
            deleted += 1

        await db.flush()
        await db.commit()
    except HTTPException:
        await db.rollback()
        raise
    except Exception as exc:
        await db.rollback()
        logger.error(
            "personality_save_failed",
            personality_id=personality_id,
            error=str(exc),
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="系统错误") from exc

    logger.info(
        "personality_saved",
        personality_id=personality_id,
        updated_placeholders=updated,
        created_placeholders=created,
        deleted_placeholders=deleted,
    )

    return {
        "success": True,
        "message": "Saved successfully",
        "updated_placeholders": updated,
        "created_placeholders": created,
        "deleted_placeholders": deleted,
    }
