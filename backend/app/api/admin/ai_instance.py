"""Admin AI Instance API endpoints.
Handles instance management including prompt variables, dimensions, and relationships.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import POSITION_MAX_VALUE
from app.core.database import get_db
from app.crud.ai import ai_instance as ai_instance_crud
from app.crud.ai.instance_dimension import update_dimension, update_dimensions_batch
from app.enums import PositionMappingAlgorithm
from app.services.admin.instance_relationship import generate_relationship_for_instance
from app.services.ai.utils.position_mapping import parse_algorithm_params
from app.utils.logging import get_logger

logger = get_logger(__name__)

ai_instance_router = APIRouter()


@ai_instance_router.post("/ai_instance/{instance_id}/save")
async def save_instance(
    instance_id: int,
    data: dict[str, Any],  # Admin API: dynamic structure with runtime validation
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Save instance prompt_variables and dimensions."""
    # Get instance
    instance = await ai_instance_crud.get(db, record_id=instance_id)
    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")

    update_data: dict[str, Any] = {}

    # Validate and update prompt_variables
    if "prompt_variables" in data:
        prompt_variables = data["prompt_variables"]
        if not isinstance(prompt_variables, dict):
            raise HTTPException(status_code=400, detail="prompt_variables must be a dict")
        update_data["prompt_variables"] = prompt_variables

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
            if not isinstance(score, int | float) or not (0 <= score <= POSITION_MAX_VALUE):
                raise HTTPException(
                    status_code=400, detail=f"score must be between 0 and {POSITION_MAX_VALUE}"
                )

            # Validate algorithm
            if algorithm not in [1, 2]:
                raise HTTPException(status_code=400, detail="Invalid algorithm")

            cleaned: dict[str, Any] = {
                "dimension_id": int(dimension_id),
                "score": int(score),
                "position_mapping_algorithm": int(algorithm),
            }

            if algorithm == PositionMappingAlgorithm.V1.value:
                params = dim_data.get("position_mapping_params", {})
                if not isinstance(params, dict):
                    raise HTTPException(
                        status_code=400, detail="position_mapping_params must be a dict"
                    )
                try:
                    cleaned["position_mapping_params"] = parse_algorithm_params(
                        PositionMappingAlgorithm.V1, params
                    )
                except ValueError as exc:
                    raise HTTPException(status_code=400, detail=str(exc)) from exc

            cleaned_dimensions.append(cleaned)

        if cleaned_dimensions:
            # Batch update only when we have valid dimensions
            result = await update_dimensions_batch(
                db, instance_id=instance_id, dimensions_data=cleaned_dimensions
            )
            updated_dims = result["updated"]
            created_dims = result["created"]

    # Optional positions mapping from preview: { dimension_id: position }
    if "positions" in data and isinstance(data["positions"], dict):
        for key, val in data["positions"].items():
            try:
                dim_id = int(key)
                pv = int(val)
                if 0 <= pv <= POSITION_MAX_VALUE:
                    await update_dimension(
                        db,
                        instance_id=instance_id,
                        dimension_id=dim_id,
                        update_data={"position": pv},
                    )
            except Exception as e:
                logger.warning(
                    "position_update_failed",
                    instance_id=instance_id,
                    dimension_id=key,
                    position=val,
                    error=str(e),
                )
                continue

    # Update relationship_id if provided
    if "relationship_id" in data and data["relationship_id"] is not None:
        try:
            relationship_id = int(data["relationship_id"])
            update_data["relationship_id"] = relationship_id
        except Exception as e:
            logger.error("update_relationship_id_failed", instance_id=instance_id, error=str(e))

    if "typing_speed_wpm" in data:
        raw_value = data["typing_speed_wpm"]
        try:
            typing_speed = int(raw_value)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=400, detail="typing_speed_wpm must be an integer"
            ) from None
        if typing_speed <= 0:
            raise HTTPException(status_code=400, detail="typing_speed_wpm must be greater than 0")
        update_data["typing_speed_wpm"] = typing_speed

    if update_data:
        await ai_instance_crud.update(db, db_obj=instance, obj_in=update_data)

    logger.info(
        "instance_saved",
        instance_id=instance_id,
        updated_dimensions=updated_dims,
        created_dimensions=created_dims,
    )

    return {
        "success": True,
        "message": "Saved successfully",
        "updated_dimensions": updated_dims,
        "created_dimensions": created_dims,
    }


@ai_instance_router.post("/ai_instance/{instance_id}/generate-relationship")
async def generate_instance_relationship(
    instance_id: int, data: dict[str, Any] | None = None, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
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

        result = await generate_relationship_for_instance(
            db, instance_id=int(instance_id), overrides=overrides, preview=preview
        )
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("message", "Generate failed"))

    except HTTPException:
        raise
    except Exception as e:
        logger.error("instance_generate_relationship_failed", instance_id=instance_id, error=str(e))
        raise HTTPException(status_code=500, detail="系统错误") from e

    else:
        return result
