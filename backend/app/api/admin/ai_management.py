"""
Admin AI Management API endpoints.
Provides AI character and template JSON field editing functionality.
"""

from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from crud.ai import (
    ai_character as character_crud,
    ai_personality as personality_crud,
    ai_personality_placeholder as placeholder_crud,
    ai_info_template as info_template_crud,
)
from utils.logging import get_logger

logger = get_logger(__name__)

ai_router = APIRouter()


@ai_router.get("/ai-personality/{personality_id}/placeholders")
async def get_personality_placeholders(
    personality_id: int, db: AsyncSession = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Get placeholders for a personality."""
    placeholders = await placeholder_crud.get_placeholders_by_personality(db, personality_id=personality_id)
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


@ai_router.post("/ai-character/{character_id}/save-json")
async def save_character_json(
    character_id: int, data: Dict[str, Any], db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Save character JSON fields (prompt_variables and score_offset_params)."""
    character = await character_crud.get(db, id=character_id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")

    update_data = {}

    # Handle prompt_variables
    if "prompt_variables" in data:
        prompt_variables = data["prompt_variables"]
        if not isinstance(prompt_variables, dict):
            raise HTTPException(status_code=400, detail="prompt_variables must be a dict")
        update_data["prompt_variables"] = prompt_variables

    # Handle score_offset_params
    if "score_offset_params" in data:
        score_offset_params = data["score_offset_params"]
        if not isinstance(score_offset_params, dict):
            raise HTTPException(status_code=400, detail="score_offset_params must be a dict")

        # Validate params based on algorithm
        if character.score_offset_algorithm == 2:  # V1 algorithm
            if "left_bias" not in score_offset_params or "right_bias" not in score_offset_params:
                raise HTTPException(
                    status_code=400, detail="left_bias and right_bias are required for V1 algorithm"
                )

            left_bias = score_offset_params["left_bias"]
            right_bias = score_offset_params["right_bias"]

            if not isinstance(left_bias, (int, float)) or not isinstance(right_bias, (int, float)):
                raise HTTPException(status_code=400, detail="Bias values must be numbers")

            if not (-100 <= left_bias <= 100) or not (-100 <= right_bias <= 100):
                raise HTTPException(status_code=400, detail="Bias values must be between -100 and 100")

        update_data["score_offset_params"] = score_offset_params

    if not update_data:
        raise HTTPException(status_code=400, detail="No data to update")

    # Update character
    await character_crud.update(db, db_obj=character, obj_in=update_data)

    logger.info("character_json_updated", character_id=character_id, fields=list(update_data.keys()))

    return {"success": True, "message": "Data saved successfully"}


@ai_router.post("/ai-info-template/{template_id}/save-json")
async def save_info_template_json(
    template_id: int, data: Dict[str, Any], db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Save info template JSON fields (prompt_variables)."""
    template = await info_template_crud.get(db, id=template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    if "prompt_variables" not in data:
        raise HTTPException(status_code=400, detail="prompt_variables is required")

    prompt_variables = data["prompt_variables"]
    if not isinstance(prompt_variables, dict):
        raise HTTPException(status_code=400, detail="prompt_variables must be a dict")

    await info_template_crud.update(db, db_obj=template, obj_in={"prompt_variables": prompt_variables})

    logger.info(
        "info_template_json_updated", template_id=template_id, variables_count=len(prompt_variables)
    )

    return {"success": True, "message": "Variables saved successfully"}


@ai_router.post("/ai-personality/{personality_id}/save-all")
async def save_personality_all(
    personality_id: int, data: Dict[str, Any], db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Save personality JSON schema and placeholders."""
    # Get personality
    personality = await personality_crud.get(db, id=personality_id)
    if not personality:
        raise HTTPException(status_code=404, detail="Personality not found")

    # 1. Update prompt and JSON Schema
    update_data = {}

    if "prompt" in data:
        prompt = data["prompt"]
        if not prompt or not prompt.strip():
            raise HTTPException(status_code=400, detail="prompt cannot be empty")
        update_data["prompt"] = prompt

    if "json_schema" in data:
        json_schema = data["json_schema"]
        if not isinstance(json_schema, dict):
            raise HTTPException(status_code=400, detail="json_schema must be a dict")
        update_data["json_schema"] = json_schema

    if update_data:
        await personality_crud.update(db, db_obj=personality, obj_in=update_data)

    # 2. Handle placeholders
    updated = 0
    created = 0

    for placeholder_data in data.get("placeholders", []):
        placeholder_id = placeholder_data.pop("id", None)

        if placeholder_id:
            # Update existing placeholder
            existing_placeholder = await placeholder_crud.get(db, id=placeholder_id)
            if existing_placeholder:
                await placeholder_crud.update(db, db_obj=existing_placeholder, obj_in=placeholder_data)
                updated += 1
        else:
            # Create new placeholder directly using model
            from models.ai.personality import AIPersonalityPlaceholder

            placeholder_data["personality_id"] = personality_id
            new_placeholder = AIPersonalityPlaceholder(**placeholder_data)
            db.add(new_placeholder)
            created += 1

    # 3. Delete placeholders
    deleted = 0
    for placeholder_id in data.get("deleted_placeholder_ids", []):
        await placeholder_crud.delete(db, id=placeholder_id)
        deleted += 1

    # Commit all changes
    await db.commit()

    logger.info(
        "personality_all_updated",
        personality_id=personality_id,
        updated=updated,
        created=created,
        deleted=deleted,
    )

    return {
        "success": True,
        "message": "Saved successfully",
        "updated_placeholders": updated,
        "created_placeholders": created,
        "deleted_placeholders": deleted,
    }


@ai_router.post("/ai-style/{style_id}/save-all")
async def save_style_complete(
    style_id: int, data: Dict[str, Any], db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Save style dimensions and relationship indexes."""
    from crud.ai import ai_style as style_crud
    from models.ai.style import AIRelationshipDimension, AIRelationshipIndex
    from sqlalchemy import delete, update

    # Get style
    style = await style_crud.get(db, id=style_id)
    if not style:
        raise HTTPException(status_code=404, detail="Style not found")

    # Get data
    dimensions_data = data.get("dimensions", [])
    deleted_dimension_ids = data.get("deleted_dimension_ids", [])
    indexes_data = data.get("indexes", [])
    deleted_index_ids = data.get("deleted_index_ids", [])

    # === Process Dimensions ===
    deleted_dims = 0
    updated_dims = 0
    created_dims = 0

    # Delete dimensions
    if deleted_dimension_ids:
        stmt = delete(AIRelationshipDimension).where(AIRelationshipDimension.id.in_(deleted_dimension_ids))
        result = await db.execute(stmt)
        deleted_dims = result.rowcount
        logger.info(
            "deleted_dimensions",
            style_id=style_id,
            deleted_count=deleted_dims,
            deleted_ids=deleted_dimension_ids,
        )

    # Update or create dimensions
    for dim_data in dimensions_data:
        dim_id = dim_data.get("id")

        if dim_id:
            # Update existing dimension
            stmt = (
                update(AIRelationshipDimension)
                .where(AIRelationshipDimension.id == dim_id)
                .values(
                    display_name=dim_data["display_name"],
                    initial_position=dim_data["initial_position"],
                )
            )
            result = await db.execute(stmt)
            if result.rowcount > 0:
                updated_dims += 1
        else:
            # Create new dimension
            new_dim = AIRelationshipDimension(
                style_id=style_id,
                name=dim_data["name"],
                display_name=dim_data["display_name"],
                initial_position=dim_data["initial_position"],
            )
            db.add(new_dim)
            created_dims += 1

    # Commit dimensions first to get IDs for new dimensions
    await db.commit()

    # === Process Indexes ===

    # Delete indexes
    deleted_indexes = 0
    if deleted_index_ids:
        stmt = delete(AIRelationshipIndex).where(AIRelationshipIndex.id.in_(deleted_index_ids))
        result = await db.execute(stmt)
        deleted_indexes = result.rowcount
        logger.info(
            "deleted_relationship_indexes",
            style_id=style_id,
            deleted_count=deleted_indexes,
            deleted_ids=deleted_index_ids,
        )

    # Update or create indexes
    updated_indexes = 0
    created_indexes = 0

    for index_data in indexes_data:
        index_id = index_data.get("id")

        if index_id:
            # Update existing index
            stmt = (
                update(AIRelationshipIndex)
                .where(AIRelationshipIndex.id == index_id)
                .values(
                    dimension_id=index_data["dimension_id"],
                    start_position=index_data["start_position"],
                    end_position=index_data["end_position"],
                    relationship_id=index_data["relationship_id"],
                    priority=index_data.get("priority", 1),
                    limit_count=index_data.get("limit_count", 0),
                )
            )
            result = await db.execute(stmt)
            if result.rowcount > 0:
                updated_indexes += 1
        else:
            # Create new index
            new_index = AIRelationshipIndex(
                style_id=style_id,
                dimension_id=index_data["dimension_id"],
                start_position=index_data["start_position"],
                end_position=index_data["end_position"],
                relationship_id=index_data["relationship_id"],
                priority=index_data.get("priority", 1),
                limit_count=index_data.get("limit_count", 0),
            )
            db.add(new_index)
            created_indexes += 1

    await db.commit()

    logger.info(
        "saved_style_complete",
        style_id=style_id,
        dimensions_updated=updated_dims,
        dimensions_created=created_dims,
        dimensions_deleted=deleted_dims,
        indexes_updated=updated_indexes,
        indexes_created=created_indexes,
        indexes_deleted=deleted_indexes,
    )

    return {
        "success": True,
        "message": "Saved successfully",
        "updated_dimensions": updated_dims,
        "created_dimensions": created_dims,
        "deleted_dimensions": deleted_dims,
        "updated_indexes": updated_indexes,
        "created_indexes": created_indexes,
        "deleted_indexes": deleted_indexes,
    }
