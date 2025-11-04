"""
Admin AI Dimension API endpoints.
Handles dimension queries and relationship mappings.
"""

from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from services.admin.style_data import (
    get_dimension_relationship_mappings as admin_get_dimension_relationship_mappings,
)
from utils.logging import get_logger

logger = get_logger(__name__)

dimension_router = APIRouter()


@dimension_router.post("/ai-dimensions/by-names")
async def get_dimensions_by_names(
    data: Dict[str, Any], db: AsyncSession = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Get dimension details by names."""
    from sqlalchemy import select
    from models.ai.style import AIDimension

    names = data.get("names", [])
    if not names:
        return []

    result = await db.execute(
        select(AIDimension).where(AIDimension.name.in_(names)).order_by(AIDimension.name)
    )
    dimensions = result.scalars().all()

    return [
        {
            "id": d.id,
            "name": d.name,
            "display_name": d.display_name,
            "description": d.description,
        }
        for d in dimensions
    ]


@dimension_router.get("/style/{style_id}/relationship-mappings")
async def list_dimension_relationship_mappings(
    style_id: int,
    limit: int | None = None,
    dimension_id: int | None = None,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """List dimension relationship mappings for a style (admin API replacement for CustomView)."""
    try:
        items = await admin_get_dimension_relationship_mappings(
            db, style_id=int(style_id), limit=limit, dimension_id=dimension_id
        )
        return {"items": items, "total": len(items), "style_id": style_id}
    except Exception as e:
        logger.error(
            "list_dimension_relationship_mappings_failed",
            style_id=style_id,
            limit=limit,
            dimension_id=dimension_id,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail="Failed to list dimension relationship mappings")
