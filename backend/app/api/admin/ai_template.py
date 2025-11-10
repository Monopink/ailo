"""
Admin AI Character Template API endpoints.
Handles character template management including prompt variables and position mapping configurations.
"""

from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from crud.ai import ai_character_template as character_template_crud
from enums.common import PositionMappingAlgorithm
from services.ai.utils.position_mapping import parse_algorithm_params
from utils.logging import get_logger

logger = get_logger(__name__)

template_router = APIRouter()


@template_router.post("/ai_character_template/{template_id}/save")
async def save_character_template(
    template_id: int, data: Dict[str, Any], db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Save character template JSON fields (prompt_variables and position_mapping_config)."""
    template = await character_template_crud.get(db, id=template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    update_data: Dict[str, Any] = {}

    # Handle prompt_variables
    if "prompt_variables" in data:
        prompt_variables = data["prompt_variables"]
        if not isinstance(prompt_variables, dict):
            raise HTTPException(status_code=400, detail="prompt_variables must be a dict")
        update_data["prompt_variables"] = prompt_variables

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
                    raise HTTPException(status_code=400, detail=f"Params for {dim_name} must be a dict")

                try:
                    dim_config["params"] = parse_algorithm_params(PositionMappingAlgorithm.V1, params)
                except ValueError as exc:
                    raise HTTPException(status_code=400, detail=str(exc))

        update_data["position_mapping_config"] = position_mapping_config

    if not update_data:
        raise HTTPException(status_code=400, detail="No data to update")

    await character_template_crud.update(db, db_obj=template, obj_in=update_data)

    logger.info(
        "character_template_json_updated",
        template_id=template_id,
        fields=list(update_data.keys()),
    )

    return {"success": True, "message": "Data saved successfully"}
