"""
Admin style dimension data services.

Provide data retrieval helpers for style-related admin endpoints.
"""

from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from utils.logging import get_logger

logger = get_logger(__name__)


SOFT_CAP = 9999  # hard-coded soft cap per admin decision


async def get_dimension_relationship_mappings(
    db: AsyncSession, *, style_id: int, limit: Optional[int] = 100, dimension_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Get dimension relationship mappings for a style with optional dimension filter.

    Args:
        db: DB session
        style_id: style id
        limit: 0 for unlimited; >0 to limit rows; None -> use default 100 and log error
        dimension_id: optional filter

    Returns:
        List of mapping rows with all fields required by admin UI
    """
    # Normalize limit
    if limit is None:
        logger.error("dimension_relationship_mappings_missing_limit", style_id=style_id)
        norm_limit = 100
    else:
        try:
            norm_limit = int(limit)
        except Exception:
            logger.error("dimension_relationship_mappings_invalid_limit", style_id=style_id, limit=limit)
            norm_limit = 100

    params: Dict[str, Any] = {"style_id": int(style_id)}
    where_extra = ""
    if dimension_id is not None:
        where_extra = " AND d.id = :dimension_id"
        params["dimension_id"] = int(dimension_id)

    base_sql = f"""
        SELECT DISTINCT
            drm.relationship_id,
            drm.dimension_id,
            d.name AS dimension_name,
            drm.start_position,
            drm.end_position,
            drm.priority,
            COALESCE(drm.limit_count, 0) AS limit_count,
            ar.name AS relationship_name,
            ar.display_name AS relationship_display_name,
            ar.prompt_fragment AS prompt_fragment
        FROM ai_dimension_relationship_mappings drm
        JOIN ai_style_dimensions asd ON asd.dimension_id = drm.dimension_id AND asd.style_id = :style_id
        JOIN ai_dimensions d ON d.id = drm.dimension_id
        JOIN ai_relationships ar ON ar.id = drm.relationship_id
        WHERE 1=1{where_extra}
        ORDER BY d.name, drm.priority DESC, drm.start_position
    """

    if norm_limit and norm_limit > 0:
        sql = base_sql + "\nLIMIT :limit"
        params["limit"] = norm_limit
    else:
        sql = base_sql

    result = await db.execute(text(sql), params)
    rows = result.fetchall()

    items = [
        {
            "relationship_id": r.relationship_id,
            "dimension_id": r.dimension_id,
            "dimension_name": r.dimension_name,
            "start_position": r.start_position,
            "end_position": r.end_position,
            "priority": r.priority,
            "limit_count": r.limit_count,
            "relationship_name": r.relationship_name,
            "relationship_display_name": r.relationship_display_name,
            "prompt_fragment": r.prompt_fragment,
        }
        for r in rows
    ]

    # Soft cap when unlimited
    if (norm_limit is None or norm_limit <= 0) and len(items) > SOFT_CAP:
        logger.info(
            "dimension_relationship_mappings_soft_capped",
            style_id=style_id,
            returned=SOFT_CAP,
            total=len(items),
        )
        items = items[:SOFT_CAP]

    return items
