"""Admin AI Personality API endpoints.
Handles personality management including prompts, schemas, and placeholders.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.crud.ai import ai_personality as personality_crud
from app.crud.ai import ai_personality_placeholder as placeholder_crud
from app.models.ai.personality import AIPersonalityPlaceholder
from app.services.ai.response_schema import generate_json_schema
from app.utils.logging import get_logger

logger = get_logger(__name__)

personality_router = APIRouter()


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
    """Save personality with auto-generated JSON schema from structured config."""
    personality = await personality_crud.get(db, record_id=personality_id)
    if not personality:
        raise HTTPException(status_code=404, detail="Personality not found")

    # Validate prompt
    prompt = data.get("prompt", "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt cannot be empty")

    # Validate schema_config
    schema_config = data.get("schema_config")
    if not schema_config or not isinstance(schema_config, dict):
        raise HTTPException(status_code=400, detail="schema_config is required")

    # Validate dimensions exist
    dimensions = schema_config.get("dimensions", [])
    if not dimensions:
        raise HTTPException(status_code=400, detail="dimensions are required")

    # Generate JSON Schema
    json_schema = generate_json_schema(schema_config)

    # Update personality
    await personality_crud.update(
        db, db_obj=personality, obj_in={"prompt": prompt, "json_schema": json_schema}
    )

    # Handle placeholders
    updated = 0
    created = 0

    for placeholder_data in data.get("placeholders", []):
        placeholder_id = placeholder_data.pop("id", None)

        if placeholder_id:
            existing_placeholder = await placeholder_crud.get(db, record_id=placeholder_id)
            if existing_placeholder:
                await placeholder_crud.update(
                    db, db_obj=existing_placeholder, obj_in=placeholder_data
                )
                updated += 1
        else:
            placeholder_data["personality_id"] = personality_id
            new_placeholder = AIPersonalityPlaceholder(**placeholder_data)
            db.add(new_placeholder)
            created += 1

    # Delete placeholders
    deleted = 0
    for placeholder_id in data.get("deleted_placeholder_ids", []):
        await placeholder_crud.remove(db, record_id=placeholder_id)
        deleted += 1

    await db.commit()

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
