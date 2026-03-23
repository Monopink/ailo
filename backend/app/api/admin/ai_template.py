"""Admin AI Template API endpoints.
Handles template management including prompt variables and position mapping configurations.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.crud.ai import ai_template as ai_template_crud
from app.enums import PositionMappingAlgorithm
from app.services.ai.utils.position_mapping import parse_algorithm_params
from app.utils.logging import get_logger

logger = get_logger(__name__)

template_router = APIRouter()


@template_router.post("/ai_template/{template_id}/save")
async def save_ai_template(
    template_id: int, data: dict[str, Any], db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Save template advanced edit (prompt_variables and position_mapping_config)."""
    template = await ai_template_crud.get(db, record_id=template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    update_data: dict[str, Any] = {}

    # Handle prompt_variables
    if "prompt_variables" in data:
        prompt_variables = data["prompt_variables"]
        if not isinstance(prompt_variables, dict):
            raise HTTPException(status_code=400, detail="prompt_variables must be a dict")
        update_data["prompt_variables"] = prompt_variables

    if "typing_speed_wpm" in data:
        raw_value = data["typing_speed_wpm"]
        try:
            typing_speed = int(raw_value)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="typing_speed_wpm must be an integer")
        if typing_speed <= 0:
            raise HTTPException(status_code=400, detail="typing_speed_wpm must be greater than 0")
        update_data["typing_speed_wpm"] = typing_speed

    # Handle position_mapping_config
    if "position_mapping_config" in data:
        position_mapping_config = data["position_mapping_config"]
        if not isinstance(position_mapping_config, dict):
            raise HTTPException(status_code=400, detail="position_mapping_config must be a dict")

        # Validate each dimension config
        for dim_name, dim_config in position_mapping_config.items():
            if not isinstance(dim_config, dict):
                raise HTTPException(status_code=400, detail=f"Config for {dim_name} must be a dict")

            algorithm = dim_config.get("algorithm", 1)
            if algorithm not in [1, 2]:
                raise HTTPException(status_code=400, detail=f"Invalid algorithm for {dim_name}")

            if algorithm == PositionMappingAlgorithm.V1.value:
                params = dim_config.get("params", {})
                if not isinstance(params, dict):
                    raise HTTPException(
                        status_code=400, detail=f"Params for {dim_name} must be a dict"
                    )

                try:
                    dim_config["params"] = parse_algorithm_params(
                        PositionMappingAlgorithm.V1, params
                    )
                except ValueError as exc:
                    raise HTTPException(status_code=400, detail=str(exc))

        update_data["position_mapping_config"] = position_mapping_config

    if not update_data:
        raise HTTPException(status_code=400, detail="No data to update")

    await ai_template_crud.update(db, db_obj=template, obj_in=update_data)

    logger.info(
        "ai_template_json_updated",
        template_id=template_id,
        fields=list(update_data.keys()),
    )

    return {"success": True, "message": "Data saved successfully"}
