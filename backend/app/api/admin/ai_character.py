"""
Admin AI Character API endpoints.
Handles character management including prompt variables, dimensions, and relationships.
"""

from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from crud.ai import ai_character as character_crud
from utils.logging import get_logger

logger = get_logger(__name__)

character_router = APIRouter()


@character_router.post("/ai_character/{character_id}/save")
async def save_character(
    character_id: int, data: Dict[str, Any], db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Save character prompt_variables and dimensions."""
    from crud.ai.character_dimension import update_dimensions_batch

    # Get character
    character = await character_crud.get(db, id=character_id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")

    # Validate and update prompt_variables
    if "prompt_variables" in data:
        prompt_variables = data["prompt_variables"]
        if not isinstance(prompt_variables, dict):
            raise HTTPException(status_code=400, detail="prompt_variables must be a dict")
        await character_crud.update(db, db_obj=character, obj_in={"prompt_variables": prompt_variables})

    # Validate and update dimensions (skip items with empty score/algorithm)
    updated_dims = 0
    created_dims = 0

    if "dimensions" in data:
        raw_dimensions = data["dimensions"]
        if not isinstance(raw_dimensions, list):
            raise HTTPException(status_code=400, detail="dimensions must be a list")

        cleaned_dimensions = []

        for dim_data in raw_dimensions:
            if not isinstance(dim_data, dict):
                raise HTTPException(status_code=400, detail="Each dimension must be a dict")

            dimension_id = dim_data.get("dimension_id")
            if dimension_id is None:
                # Skip if no dimension id
                continue

            score = dim_data.get("score")
            algorithm = dim_data.get("position_mapping_algorithm")

            # Skip if score or algorithm missing/empty
            if score is None or algorithm is None:
                continue

            # Validate score
            if not isinstance(score, (int, float)) or not (0 <= score <= 1000):
                raise HTTPException(status_code=400, detail="score must be between 0 and 1000")

            # Validate algorithm
            if algorithm not in [1, 2]:
                raise HTTPException(status_code=400, detail="Invalid algorithm")

            cleaned: Dict[str, Any] = {
                "dimension_id": int(dimension_id),
                "score": int(score),
                "position_mapping_algorithm": int(algorithm),
            }

            if algorithm == 2:
                params = dim_data.get("position_mapping_params", {})
                if not isinstance(params, dict):
                    raise HTTPException(status_code=400, detail="position_mapping_params must be a dict")
                left_bias = params.get("left_bias", 0)
                right_bias = params.get("right_bias", 0)
                if not isinstance(left_bias, (int, float)) or not isinstance(right_bias, (int, float)):
                    raise HTTPException(status_code=400, detail="Bias values must be numbers")
                if not (-100 <= left_bias <= 100) or not (-100 <= right_bias <= 100):
                    raise HTTPException(status_code=400, detail="Bias values must be between -100 and 100")
                cleaned["position_mapping_params"] = {
                    "left_bias": int(left_bias),
                    "right_bias": int(right_bias),
                }

            cleaned_dimensions.append(cleaned)

        if cleaned_dimensions:
            # Batch update only when we have valid dimensions
            result = await update_dimensions_batch(
                db, character_id=character_id, dimensions_data=cleaned_dimensions
            )
            updated_dims = result["updated"]
            created_dims = result["created"]

    # Optional positions mapping from preview: { dimension_id: position }
    if "positions" in data and isinstance(data["positions"], dict):
        from crud.ai.character_dimension import update_dimension

        for key, val in data["positions"].items():
            try:
                dim_id = int(key)
                pv = int(val)
                if 0 <= pv <= 1000:
                    await update_dimension(
                        db, character_id=character_id, dimension_id=dim_id, update_data={"position": pv}
                    )
            except Exception:
                continue

    # Update relationship_id if provided
    if "relationship_id" in data and data["relationship_id"] is not None:
        try:
            relationship_id = int(data["relationship_id"])
            await character_crud.update(db, db_obj=character, obj_in={"relationship_id": relationship_id})
        except Exception as e:
            logger.error("update_relationship_id_failed", character_id=character_id, error=str(e))

    logger.info(
        "character_saved",
        character_id=character_id,
        updated_dimensions=updated_dims,
        created_dimensions=created_dims,
    )

    return {
        "success": True,
        "message": "Saved successfully",
        "updated_dimensions": updated_dims,
        "created_dimensions": created_dims,
    }


@character_router.post("/ai_character/{character_id}/generate-relationship")
async def generate_character_relationship(
    character_id: int, data: Dict[str, Any] | None = None, db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Preview or persist generate-relationship using admin service (overrides + preview)."""
    try:
        overrides = None
        preview = True
        if isinstance(data, dict):
            overrides = data.get("overrides")
            pv = data.get("preview")
            if pv is not None:
                try:
                    preview = bool(pv)
                except Exception:
                    preview = True

        from services.admin.position_mapping import generate_relationship_for_character

        result = await generate_relationship_for_character(
            db, character_id=int(character_id), overrides=overrides, preview=preview
        )
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("message", "Generate failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("generate_relationship_service_failed", character_id=character_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to generate relationship")


@character_router.put("/ai_character/{character_id}/dimension/{dimension_id}")
async def update_character_dimension(
    character_id: int, dimension_id: int, data: Dict[str, Any], db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    DEPRECATED: Use /ai_character/{character_id}/save instead.

    Update character dimension (score, algorithm, params).
    """
    from crud.ai.character_dimension import update_dimension

    character = await character_crud.get(db, id=character_id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")

    # Validate data
    if "score" not in data:
        raise HTTPException(status_code=400, detail="score is required")

    score = data["score"]
    if not isinstance(score, (int, float)) or not (0 <= score <= 1000):
        raise HTTPException(status_code=400, detail="score must be between 0 and 1000")

    algorithm = data.get("position_mapping_algorithm", 1)
    if algorithm not in [1, 2]:
        raise HTTPException(status_code=400, detail="Invalid algorithm")

    params = data.get("position_mapping_params", {})
    if algorithm == 2:
        if not isinstance(params, dict):
            raise HTTPException(status_code=400, detail="position_mapping_params must be a dict")

        left_bias = params.get("left_bias", 0)
        right_bias = params.get("right_bias", 0)

        if not isinstance(left_bias, (int, float)) or not isinstance(right_bias, (int, float)):
            raise HTTPException(status_code=400, detail="Bias values must be numbers")

        if not (-100 <= left_bias <= 100) or not (-100 <= right_bias <= 100):
            raise HTTPException(status_code=400, detail="Bias values must be between -100 and 100")

    # Update dimension - fix function call signature
    update_data = {
        "score": int(score),
        "position_mapping_algorithm": algorithm,
        "position_mapping_params": params,
    }
    success = await update_dimension(
        db, character_id=character_id, dimension_id=dimension_id, update_data=update_data
    )

    if not success:
        raise HTTPException(status_code=404, detail="Dimension not found")

    logger.info("character_dimension_updated", character_id=character_id, dimension_id=dimension_id)

    return {"success": True, "message": "Dimension updated successfully"}
