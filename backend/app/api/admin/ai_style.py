"""Admin AI Style API endpoints.
Handles style management including dimensions, associations, and relationship mappings.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import POSITION_MAX_VALUE
from app.core.database import get_db
from app.crud.ai import ai_style as style_crud
from app.models.ai.instance import AIInstance
from app.models.ai.style import (
    AIDimension,
    AIDimensionRelationshipMapping,
    AIStyle,
    AIStyleDimension,
)
from app.models.ai.template import AITemplate
from app.utils.logging import get_logger

logger = get_logger(__name__)

style_router = APIRouter()

DIMENSION_NAME_MAX_LENGTH = 50
DIMENSION_DISPLAY_NAME_MAX_LENGTH = 100


def _resolve_dimension_key(dimension_data: dict[str, Any]) -> int | None:
    """Resolve a stable per-request dimension key from persisted or temporary IDs."""
    raw_key = dimension_data.get("dimension_id", dimension_data.get("temp_id"))
    if raw_key is None:
        return None
    try:
        return int(raw_key)
    except (TypeError, ValueError):
        return None


def _parse_dimension_id(raw_value: object) -> int | None:
    """Parse dimension IDs from payload, returning None for invalid values."""
    if raw_value is None or isinstance(raw_value, bool):
        return None

    if isinstance(raw_value, int):
        parsed = raw_value
    elif isinstance(raw_value, str):
        text = raw_value.strip()
        if text == "":
            return None
        try:
            parsed = int(text)
        except ValueError:
            return None
    else:
        return None

    return parsed if parsed > 0 else None


def _validate_dimension_name(raw_value: object) -> str:
    """Validate and normalize a new dimension name."""
    if not isinstance(raw_value, str):
        raise HTTPException(status_code=400, detail="name is required for new dimensions")
    value = raw_value.strip()
    if not value:
        raise HTTPException(status_code=400, detail="name is required for new dimensions")
    if len(value) > DIMENSION_NAME_MAX_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"dimension name must be at most {DIMENSION_NAME_MAX_LENGTH} characters",
        )
    return value


def _validate_dimension_display_name(raw_value: object) -> str:
    """Validate and normalize display_name when explicitly provided."""
    if not isinstance(raw_value, str):
        raise HTTPException(status_code=400, detail="dimension display_name must be a string")
    value = raw_value.strip()
    if len(value) > DIMENSION_DISPLAY_NAME_MAX_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=(
                "dimension display_name must be at most "
                f"{DIMENSION_DISPLAY_NAME_MAX_LENGTH} characters"
            ),
        )
    return value


async def _style_has_references(db: AsyncSession, style_id: int) -> bool:
    """Return True if any instance or template references this style."""
    instance_ref = await db.execute(
        select(AIInstance.id).where(AIInstance.style_id == style_id).limit(1)
    )
    if instance_ref.scalar_one_or_none() is not None:
        return True

    template_ref = await db.execute(
        select(AITemplate.id).where(AITemplate.style_id == style_id).limit(1)
    )
    return template_ref.scalar_one_or_none() is not None


def _collect_dimension_set_changes(
    *,
    dimensions_data: list[dict[str, Any]],
    removed_association_dimension_ids: list[Any],
    existing_dimension_ids: set[int],
) -> tuple[set[int], set[int], bool]:
    """Return added_existing_ids, removed_existing_ids, has_new_dimension_creation."""
    added_existing_ids: set[int] = set()
    has_new_dimension_creation = False

    for dim_data in dimensions_data:
        dimension_id = _parse_dimension_id(dim_data.get("dimension_id"))
        if dimension_id is None:
            has_new_dimension_creation = True
            continue
        if dimension_id not in existing_dimension_ids:
            added_existing_ids.add(dimension_id)

    removed_ids = {
        parsed
        for parsed in (_parse_dimension_id(raw_id) for raw_id in removed_association_dimension_ids)
        if parsed is not None
    }
    removed_existing_ids = removed_ids.intersection(existing_dimension_ids)
    return added_existing_ids, removed_existing_ids, has_new_dimension_creation


def _validate_initial_position_priority_uniqueness(
    dimensions_data: list[dict[str, Any]],
    mappings_data: list[dict[str, Any]],
) -> list[str]:
    """Validate that each dimension's initial position can resolve a unique top-priority mapping.

    Overlapping ranges are allowed. This check only blocks the case where the initial position
    hits multiple mappings and the smallest priority value is shared by more than one mapping.
    """
    dimension_positions: dict[int, int] = {}
    dimension_labels: dict[int, str] = {}

    for dim_data in dimensions_data:
        dimension_key = _resolve_dimension_key(dim_data)
        if dimension_key is None:
            continue

        init_pos = dim_data.get("initial_position")
        if not isinstance(init_pos, int):
            continue

        dimension_positions[dimension_key] = init_pos
        label = dim_data.get("display_name") or dim_data.get("name")
        dimension_labels[dimension_key] = str(label or f"dimension_id={dimension_key}")

    candidates_by_dimension: dict[int, list[dict[str, int]]] = {}
    for mapping_data in mappings_data:
        raw_dimension_id = mapping_data.get("dimension_id")
        if raw_dimension_id is None:
            continue
        try:
            dimension_id = int(raw_dimension_id)
        except (TypeError, ValueError):
            continue

        if dimension_id not in dimension_positions:
            continue

        start_position = mapping_data.get("start_position")
        end_position = mapping_data.get("end_position")
        relationship_id = mapping_data.get("relationship_id")
        if not (
            isinstance(start_position, int)
            and isinstance(end_position, int)
            and isinstance(relationship_id, int)
        ):
            continue

        position = dimension_positions[dimension_id]
        if start_position <= position <= end_position:
            candidates_by_dimension.setdefault(dimension_id, []).append(
                {
                    "relationship_id": relationship_id,
                    "start_position": start_position,
                    "end_position": end_position,
                    "priority": int(mapping_data.get("priority", 1) or 1),
                }
            )

    errors: list[str] = []
    for dimension_id, candidates in candidates_by_dimension.items():
        if len(candidates) <= 1:
            continue

        top_priority = min(candidate["priority"] for candidate in candidates)
        top_candidates = [
            candidate for candidate in candidates if candidate["priority"] == top_priority
        ]
        if len(top_candidates) <= 1:
            continue

        candidates_text = ", ".join(
            (
                f"relationship_id={candidate['relationship_id']} "
                f"range={candidate['start_position']}-{candidate['end_position']}"
            )
            for candidate in top_candidates
        )
        errors.append(
            "Initial position "
            f"{dimension_positions[dimension_id]} for dimension "
            f"{dimension_labels.get(dimension_id, f'dimension_id={dimension_id}')}"
            f" matches multiple highest-priority mappings (priority={top_priority}): "
            f"{candidates_text}"
        )

    return errors


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
    style = await style_crud.get(db, record_id=style_id)
    if not style:
        raise HTTPException(status_code=404, detail="Style not found")

    # Normalize input payload
    dimensions_data = data.get("dimensions", []) or []
    removed_association_dimension_ids = data.get("removed_association_dimension_ids", []) or []
    mappings_data = data.get("mappings", []) or []
    deleted_mapping_ids = data.get("deleted_mapping_ids", []) or []

    original_assoc_result = await db.execute(
        select(AIStyleDimension.dimension_id).where(AIStyleDimension.style_id == style_id)
    )
    original_dimension_ids = {row[0] for row in original_assoc_result.fetchall()}

    style_has_references = await _style_has_references(db, style_id)
    if style_has_references:
        added_existing_ids, removed_existing_ids, has_new_dimension_creation = (
            _collect_dimension_set_changes(
                dimensions_data=dimensions_data,
                removed_association_dimension_ids=removed_association_dimension_ids,
                existing_dimension_ids=original_dimension_ids,
            )
        )
        if added_existing_ids or removed_existing_ids or has_new_dimension_creation:
            raise HTTPException(
                status_code=400,
                detail=(
                    "cannot change style dimension set because this style is referenced "
                    "by instances or templates"
                ),
            )

    uniqueness_errors = _validate_initial_position_priority_uniqueness(
        dimensions_data=dimensions_data,
        mappings_data=mappings_data,
    )
    if uniqueness_errors:
        raise HTTPException(status_code=400, detail="; ".join(uniqueness_errors))

    # === Remove associations (style-dimension only) ===
    deleted_associations = 0
    if removed_association_dimension_ids:
        stmt = delete(AIStyleDimension).where(
            AIStyleDimension.style_id == style_id,
            AIStyleDimension.dimension_id.in_(removed_association_dimension_ids),
        )
        delete_result = await db.execute(stmt)
        deleted_associations = delete_result.rowcount or 0
        logger.info(
            "style_dimension_associations_removed",
            style_id=style_id,
            removed_count=deleted_associations,
            removed_dimension_ids=removed_association_dimension_ids,
        )

    # === Upsert dimensions & associations ===
    # Load existing associations for fast lookup
    assoc_result: Any = await db.execute(
        select(AIStyleDimension).where(AIStyleDimension.style_id == style_id)
    )
    existing_associations = {asd.dimension_id: asd for asd in assoc_result.scalars().all()}

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
        if not isinstance(init_pos, int) or not (0 <= init_pos <= POSITION_MAX_VALUE):
            raise HTTPException(
                status_code=400,
                detail=f"initial_position must be between 0 and {POSITION_MAX_VALUE}",
            )

        dimension_id = _parse_dimension_id(dim_data.get("dimension_id"))

        # New dimension creation path (copy/new)
        if dimension_id is None:
            dimension_name = _validate_dimension_name(dim_data.get("name"))
            normalized_display_name: str | None = None
            if dim_data.get("display_name") is not None:
                normalized_display_name = _validate_dimension_display_name(
                    dim_data.get("display_name")
                )

            # Reuse existing dimension with same name to avoid uniqueness violations
            existing_dim_result = await db.execute(
                select(AIDimension).where(AIDimension.name == dimension_name)
            )
            existing_dim = existing_dim_result.scalar_one_or_none()

            if existing_dim:
                raise HTTPException(status_code=400, detail="dimension name already exists")
            new_dimension = AIDimension(
                name=dimension_name,
                display_name=normalized_display_name,
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
                update_fields["display_name"] = _validate_dimension_display_name(
                    dim_data.get("display_name")
                )
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
        delete_stmt = delete(AIDimensionRelationshipMapping).where(
            AIDimensionRelationshipMapping.id.in_(deleted_mapping_ids)
        )
        mapping_delete_result = await db.execute(delete_stmt)
        deleted_mappings = mapping_delete_result.rowcount or 0
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
        if (
            not isinstance(sp, int)
            or not isinstance(ep, int)
            or not (0 <= sp <= ep <= POSITION_MAX_VALUE)
        ):
            raise HTTPException(status_code=400, detail="Invalid start/end position for mapping")

        mapping_id = mapping_data.get("id")

        if mapping_id:
            # Update existing mapping (global)
            update_stmt = (
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
            update_result = await db.execute(update_stmt)
            if (update_result.rowcount or 0) > 0:
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


@style_router.get("/style/{style_id}/available-dimensions/search")
async def search_available_dimensions(
    style_id: int,
    q: str = Query(default="", max_length=100),
    limit: int = Query(default=20, ge=1, le=50),
    page: int = Query(default=1, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Search dimensions that are not yet associated with the current style."""
    style = await style_crud.get(db, record_id=style_id)
    if style is None:
        raise HTTPException(status_code=404, detail="Style not found")

    query = q.strip()
    offset = (page - 1) * limit

    used_dimension_ids = select(AIStyleDimension.dimension_id).where(
        AIStyleDimension.style_id == style_id
    )
    stmt = select(AIDimension).where(~AIDimension.id.in_(used_dimension_ids))

    if query:
        stmt = stmt.where(
            or_(
                AIDimension.name.ilike(f"%{query}%"),
                AIDimension.display_name.ilike(f"%{query}%"),
            )
        )

    result = await db.execute(
        stmt.order_by(
            AIDimension.display_name.asc().nulls_last(),
            AIDimension.name.asc(),
            AIDimension.id.asc(),
        )
        .offset(offset)
        .limit(limit + 1)
    )
    dimensions = result.scalars().all()
    has_more = len(dimensions) > limit
    dimensions = dimensions[:limit]

    dimension_ids = [dimension.id for dimension in dimensions]
    mappings_by_dimension: dict[int, list[dict[str, Any]]] = {}
    if dimension_ids:
        mapping_result = await db.execute(
            select(AIDimensionRelationshipMapping)
            .where(AIDimensionRelationshipMapping.dimension_id.in_(dimension_ids))
            .order_by(
                AIDimensionRelationshipMapping.dimension_id.asc(),
                AIDimensionRelationshipMapping.priority.asc(),
                AIDimensionRelationshipMapping.start_position.asc(),
                AIDimensionRelationshipMapping.end_position.asc(),
                AIDimensionRelationshipMapping.id.asc(),
            )
        )
        for mapping in mapping_result.scalars().all():
            mappings_by_dimension.setdefault(mapping.dimension_id, []).append(
                {
                    "id": mapping.id,
                    "start_position": mapping.start_position,
                    "end_position": mapping.end_position,
                    "relationship_id": mapping.relationship_id,
                    "priority": mapping.priority,
                    "limit_count": mapping.limit_count,
                }
            )

    items = []
    for dimension in dimensions:
        display_name = dimension.display_name or dimension.name
        items.append(
            {
                "id": str(dimension.id),
                "text": f"{display_name} ({dimension.name})",
                "meta": {
                    "dimension_id": dimension.id,
                    "name": dimension.name,
                    "display_name": dimension.display_name,
                    "description": dimension.description,
                    "mappings": mappings_by_dimension.get(dimension.id, []),
                },
            }
        )

    return {"items": items, "has_more": has_more}


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
