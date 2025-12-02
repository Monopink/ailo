"""
Admin AI Style API endpoints.
Handles style management including dimensions, associations, and relationship mappings.
"""

from typing import Any

from core.database import get_db
from crud.ai import ai_style as style_crud
from fastapi import APIRouter, Depends, HTTPException
from models.ai.style import AIDimension, AIDimensionRelationshipMapping, AIStyle, AIStyleDimension
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from utils.logging import get_logger

logger = get_logger(__name__)

style_router = APIRouter()


@style_router.get("/ai_style/{style_id}/dimensions")
async def get_style_dimensions(
    style_id: int, db: AsyncSession = Depends(get_db)
) -> list[dict[str, Any]]:
    """Get dimensions for a style."""
    result = await db.execute(
        select(AIDimension)
        .join(AIStyleDimension, AIStyleDimension.dimension_id == AIDimension.id)
        .where(AIStyleDimension.style_id == style_id)
        .order_by(AIDimension.name)
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


@style_router.post("/ai_style/{style_id}/save")
async def save_style_complete(
    style_id: int, data: dict[str, Any], db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Save style dimensions and relationship mappings (normalized, strict validation).

    Responsibilitiai_style/
    - Only persists data; does not format UI responses.
    - Enforces invariants: no defaults, proper ranges, and referential checks.
    """
    # Get style
    style = await style_crud.get(db, id=style_id)
    if not style:
        raise HTTPException(status_code=404, detail="Style not found")

    # Normalize input payload
    dimensions_data = data.get("dimensions", []) or []
    # Backward compatibility: deleted_dimension_ids were previously used for association removal
    deleted_dimension_ids = data.get("deleted_dimension_ids", []) or []
    removed_association_dimension_ids = (
        data.get("removed_association_dimension_ids", []) or deleted_dimension_ids
    )
    deleted_dimension_ids = data.get("deleted_dimension_ids", []) or []
    mappings_data = data.get("mappings", []) or []
    deleted_mapping_ids = data.get("deleted_mapping_ids", []) or []

    # === Remove associations (style-dimension only) ===
    deleted_associations = 0
    if removed_association_dimension_ids:
        stmt = delete(AIStyleDimension).where(
            AIStyleDimension.style_id == style_id,
            AIStyleDimension.dimension_id.in_(removed_association_dimension_ids),
        )
        result = await db.execute(stmt)
        deleted_associations = result.rowcount or 0
        logger.info(
            "style_dimension_associations_removed",
            style_id=style_id,
            removed_count=deleted_associations,
            removed_dimension_ids=removed_association_dimension_ids,
        )

    # === Upsert dimensions & associations ===
    # Load existing associations for fast lookup
    result = await db.execute(select(AIStyleDimension).where(AIStyleDimension.style_id == style_id))
    existing_associations = {asd.dimension_id: asd for asd in result.scalars().all()}

    updated_dims = 0
    created_dims = 0

    # Map negative temp_id -> new dimension_id
    temp_to_new_dim_id: dict[int, int] = {}

    for dim_data in dimensions_data:
        # Validate initial_position strictly (no defaults)
        if "initial_position" not in dim_data or dim_data["initial_position"] is None:
            raise HTTPException(
                status_code=400, detail="initial_position is required for each dimension"
            )
        init_pos = dim_data["initial_position"]
        if not isinstance(init_pos, (int,)) or not (0 <= init_pos <= 1000):
            raise HTTPException(
                status_code=400, detail="initial_position must be between 0 and 1000"
            )

        dimension_id = dim_data.get("dimension_id")

        # New dimension creation path (copy/new)
        if not dimension_id:
            if "name" not in dim_data or not dim_data["name"]:
                raise HTTPException(status_code=400, detail="name is required for new dimensions")

            # Reuse existing dimension with same name to avoid uniqueness violations
            existing_dim_result = await db.execute(
                select(AIDimension).where(AIDimension.name == dim_data["name"])
            )
            existing_dim = existing_dim_result.scalar_one_or_none()

            if existing_dim:
                raise HTTPException(status_code=400, detail="dimension name already exists")
            new_dimension = AIDimension(
                name=dim_data["name"],
                display_name=dim_data.get("display_name"),
                description=dim_data.get("description"),
            )
            db.add(new_dimension)
            await db.flush()
            dimension_id = new_dimension.id

            # Register temp_id mapping if present
            if isinstance(dim_data.get("temp_id"), int) and dim_data["temp_id"] < 0:
                temp_to_new_dim_id[dim_data["temp_id"]] = dimension_id

        # Upsert association (style_id, dimension_id)
        if dimension_id in existing_associations:
            assoc = existing_associations[dimension_id]
            assoc.initial_position = init_pos
            updated_dims += 1
        else:
            db.add(
                AIStyleDimension(
                    style_id=style_id,
                    dimension_id=dimension_id,
                    initial_position=init_pos,
                )
            )
            created_dims += 1

        # Optionally update dimension metadata if provided
        if dim_data.get("display_name") is not None or dim_data.get("description") is not None:
            update_fields = {}
            if dim_data.get("display_name") is not None:
                update_fields["display_name"] = dim_data.get("display_name")
            if dim_data.get("description") is not None:
                update_fields["description"] = dim_data.get("description")
            if update_fields:
                await db.execute(
                    update(AIDimension)
                    .where(AIDimension.id == dimension_id)
                    .values(**update_fields)
                )

    # Commit dimension and association changes first (IDs are now stable)
    await db.commit()

    # === Process Relationship Mappings (Global) ===
    # Delete mappings
    deleted_mappings = 0
    if deleted_mapping_ids:
        stmt = delete(AIDimensionRelationshipMapping).where(
            AIDimensionRelationshipMapping.id.in_(deleted_mapping_ids)
        )
        result = await db.execute(stmt)
        deleted_mappings = result.rowcount or 0
        logger.info(
            "deleted_dimension_relationship_mappings",
            style_id=style_id,
            deleted_count=deleted_mappings,
            deleted_ids=deleted_mapping_ids,
        )

    # Validate and upsert mappings
    updated_mappings = 0
    created_mappings = 0

    for mapping_data in mappings_data:
        # Resolve dimension_id from temp_id if needed
        dim_id = mapping_data.get("dimension_id")
        if isinstance(dim_id, int) and dim_id < 0 and dim_id in temp_to_new_dim_id:
            dim_id = temp_to_new_dim_id[dim_id]

        # Strict validation
        for key in ("start_position", "end_position", "relationship_id"):
            if key not in mapping_data or mapping_data[key] is None:
                raise HTTPException(status_code=400, detail=f"{key} is required for mapping")
        sp = mapping_data["start_position"]
        ep = mapping_data["end_position"]
        if not isinstance(sp, int) or not isinstance(ep, int) or not (0 <= sp <= ep <= 1000):
            raise HTTPException(status_code=400, detail="Invalid start/end position for mapping")

        mapping_id = mapping_data.get("id")

        if mapping_id:
            # Update existing mapping (global)
            stmt = (
                update(AIDimensionRelationshipMapping)
                .where(AIDimensionRelationshipMapping.id == mapping_id)
                .values(
                    dimension_id=dim_id,
                    start_position=sp,
                    end_position=ep,
                    relationship_id=mapping_data["relationship_id"],
                    priority=mapping_data.get("priority", 1),
                    limit_count=mapping_data.get("limit_count"),
                )
            )
            result = await db.execute(stmt)
            if (result.rowcount or 0) > 0:
                updated_mappings += 1
        else:
            # Create new mapping (global)
            db.add(
                AIDimensionRelationshipMapping(
                    dimension_id=dim_id,
                    start_position=sp,
                    end_position=ep,
                    relationship_id=mapping_data["relationship_id"],
                    priority=mapping_data.get("priority", 1),
                    limit_count=mapping_data.get("limit_count"),
                )
            )
            created_mappings += 1

    await db.commit()

    # === Optionally delete dimensions (only if truly unused) ===
    deleted_dimensions = 0
    if deleted_dimension_ids:
        # Verify none are used by any style and have no mappings
        # Check associations
        assoc_result = await db.execute(
            select(AIStyleDimension.dimension_id).where(
                AIStyleDimension.dimension_id.in_(deleted_dimension_ids)
            )
        )
        in_use_ids = {row[0] for row in assoc_result.fetchall()}
        if in_use_ids:
            raise HTTPException(
                status_code=400, detail=f"Dimensions still in use: {sorted(in_use_ids)}"
            )

        # Check mappings
        map_result = await db.execute(
            select(AIDimensionRelationshipMapping.dimension_id).where(
                AIDimensionRelationshipMapping.dimension_id.in_(deleted_dimension_ids)
            )
        )
        has_mapped = {row[0] for row in map_result.fetchall()}
        if has_mapped:
            raise HTTPException(
                status_code=400, detail=f"Dimensions still have mappings: {sorted(has_mapped)}"
            )

        # Safe to delete
        del_stmt = delete(AIDimension).where(AIDimension.id.in_(deleted_dimension_ids))
        result = await db.execute(del_stmt)
        deleted_dimensions = result.rowcount or 0
        await db.commit()
        logger.info(
            "deleted_dimensions",
            style_id=style_id,
            deleted_count=deleted_dimensions,
            deleted_ids=deleted_dimension_ids,
        )

    logger.info(
        "saved_style_complete",
        style_id=style_id,
        dimensions_updated=updated_dims,
        dimensions_created=created_dims,
        associations_removed=deleted_associations,
        dimensions_deleted=deleted_dimensions,
        mappings_updated=updated_mappings,
        mappings_created=created_mappings,
        mappings_deleted=deleted_mappings,
    )

    return {
        "success": True,
        "message": "Saved successfully",
        "updated_dimensions": updated_dims,
        "created_dimensions": created_dims,
        "deleted_associations": deleted_associations,
        "deleted_dimensions": deleted_dimensions,
        "updated_mappings": updated_mappings,
        "created_mappings": created_mappings,
        "deleted_mappings": deleted_mappings,
    }


@style_router.get("/style/{style_id}/available-dimensions")
async def get_available_dimensions(
    style_id: int, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Get dimensions not yet added to this style."""
    # Get dimensions already in this style
    existing_stmt = select(AIStyleDimension.dimension_id).where(
        AIStyleDimension.style_id == style_id
    )
    existing_result = await db.execute(existing_stmt)
    existing_ids = {row[0] for row in existing_result.fetchall()}

    # Get all dimensions not in this style
    stmt = select(AIDimension).where(~AIDimension.id.in_(existing_ids))
    result = await db.execute(stmt)
    dimensions = result.scalars().all()

    # Get mappings for each dimension (include id for updating globally)
    items = []
    for d in dimensions:
        mappings_stmt = select(AIDimensionRelationshipMapping).where(
            AIDimensionRelationshipMapping.dimension_id == d.id
        )
        mappings_result = await db.execute(mappings_stmt)
        mappings = mappings_result.scalars().all()

        items.append(
            {
                "id": d.id,
                "name": d.name,
                "display_name": d.display_name,
                "description": d.description,
                "initial_position": None,
                "mappings": [
                    {
                        "id": idx.id,
                        "start_position": idx.start_position,
                        "end_position": idx.end_position,
                        "relationship_id": idx.relationship_id,
                        "priority": idx.priority,
                        "limit_count": idx.limit_count,
                    }
                    for idx in mappings
                ],
            }
        )

    return {"items": items}


@style_router.get("/style/{style_id}/dimension/{dimension_id}/other-styles")
async def get_other_styles_using_dimension(
    style_id: int, dimension_id: int, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """List other styles using the given dimension (exclude current style)."""
    result = await db.execute(
        select(AIStyle)
        .join(AIStyleDimension, AIStyleDimension.style_id == AIStyle.id)
        .where(
            AIStyleDimension.dimension_id == dimension_id,
            AIStyle.id != style_id,
        )
        .order_by(AIStyle.display_name)
    )
    styles = result.scalars().all()
    items = [{"id": s.id, "display_name": s.display_name} for s in styles]
    return {"items": items, "count": len(items)}
