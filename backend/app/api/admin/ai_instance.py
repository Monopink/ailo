"""Admin AI Instance API endpoints.
Handles instance management including prompt variables, dimensions, and relationships.
"""

from typing import cast

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import POSITION_MAX_VALUE
from app.core.database import get_db
from app.crud.ai import ai_instance as ai_instance_crud
from app.crud.ai.instance_dimension import update_dimensions_batch
from app.enums import AIInstanceStatus, PositionMappingAlgorithm
from app.models.ai.instance import AIInstance
from app.models.ai.instance_dimension import AIInstanceDimension
from app.models.ai.memory import AIInstanceMemory
from app.services.admin.instance_relationship import generate_relationship_for_instance
from app.services.ai.memory.memory_policy_service import (
    ORIGIN_ADMIN,
    archive_recent_over_limit,
    lock_instance_for_memory_write,
    remove_memory_by_id_with_policy,
    upsert_memory_with_policy,
)
from app.services.ai.utils.position_mapping import parse_algorithm_params
from app.type_defs import JSONDict
from app.utils.logging import get_logger

logger = get_logger(__name__)

ai_instance_router = APIRouter()
MEMORY_IMPORTANCE_MIN = 1
MEMORY_IMPORTANCE_MAX = 10


def _coerce_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        raw = value.strip()
        if raw == "":
            return None
        try:
            return int(raw)
        except ValueError:
            return None
    return None


def _coerce_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    return text


def _coerce_source_message_id(value: object) -> int | None:
    parsed = _coerce_int(value)
    if parsed is None or parsed <= 0:
        return None
    return parsed


def _parse_memory_changes(payload: object) -> dict[str, list[object]]:
    if not isinstance(payload, dict):
        return {"create": [], "update": [], "archive_ids": []}

    create_items = payload.get("create")
    update_items = payload.get("update")
    archive_ids = payload.get("archive_ids")

    return {
        "create": create_items if isinstance(create_items, list) else [],
        "update": update_items if isinstance(update_items, list) else [],
        "archive_ids": archive_ids if isinstance(archive_ids, list) else [],
    }


def _validate_instance_memory_payload(payload: object) -> tuple[str, int, str, int | None]:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid memory payload")

    payload_dict = payload
    memory_type = payload_dict.get("memory_type")
    if not isinstance(memory_type, str) or memory_type not in {"core", "recent"}:
        raise HTTPException(status_code=400, detail="memory_type must be core or recent")

    importance = _coerce_int(payload_dict.get("importance"))
    if (
        importance is None
        or importance < MEMORY_IMPORTANCE_MIN
        or importance > MEMORY_IMPORTANCE_MAX
    ):
        raise HTTPException(status_code=400, detail="importance must be between 1 and 10")

    content = _coerce_text(payload_dict.get("content"))
    if content is None:
        raise HTTPException(status_code=400, detail="content is required")

    source_message_id = _coerce_source_message_id(payload_dict.get("source_message_id"))
    return memory_type, importance, content, source_message_id


async def _apply_instance_memory_changes(
    db: AsyncSession,
    *,
    instance: AIInstance,
    memory_changes: dict[str, list[object]],
) -> dict[str, int]:
    created = 0
    updated = 0
    archived = 0

    create_items = memory_changes["create"]
    update_items = memory_changes["update"]
    archive_ids_raw = memory_changes["archive_ids"]

    for item in create_items:
        memory_type, importance, content, source_message_id = _validate_instance_memory_payload(
            item
        )
        memory, _ = await upsert_memory_with_policy(
            db,
            instance=instance,
            memory_type=memory_type,
            content=content,
            importance=importance,
            origin=ORIGIN_ADMIN,
            source_message_id=source_message_id,
        )
        if memory is None:
            raise HTTPException(status_code=400, detail="Invalid memory create payload")
        created += 1

    for item in update_items:
        if not isinstance(item, dict):
            raise HTTPException(status_code=400, detail="Invalid memory update payload")
        memory_id = _coerce_int(item.get("id"))
        if memory_id is None:
            raise HTTPException(status_code=400, detail="memory update id is required")
        stmt = select(AIInstanceMemory).where(
            AIInstanceMemory.id == memory_id,
            AIInstanceMemory.instance_id == instance.id,
            AIInstanceMemory.status == 1,
        )
        result = await db.execute(stmt)
        memory = result.scalar_one_or_none()
        if memory is None:
            raise HTTPException(status_code=404, detail=f"Instance memory not found: {memory_id}")

        memory_type, importance, content, source_message_id = _validate_instance_memory_payload(
            item
        )

        memory.status = 2
        upserted, _ = await upsert_memory_with_policy(
            db,
            instance=instance,
            memory_type=memory_type,
            content=content,
            importance=importance,
            origin=ORIGIN_ADMIN,
            source_message_id=source_message_id,
        )
        if upserted is None:
            raise HTTPException(status_code=400, detail="Invalid memory update payload")
        updated += 1

    archive_ids: list[int] = []
    for raw_id in archive_ids_raw:
        parsed_id = _coerce_int(raw_id)
        if parsed_id is None:
            raise HTTPException(status_code=400, detail="archive_ids must contain valid integers")
        archive_ids.append(parsed_id)

    for memory_id in archive_ids:
        removed = await remove_memory_by_id_with_policy(
            db,
            instance_id=instance.id,
            memory_id=memory_id,
            origin=ORIGIN_ADMIN,
        )
        if not removed:
            raise HTTPException(
                status_code=400,
                detail=f"Memory cannot be archived: {memory_id}",
            )
        archived += 1

    if created > 0 or updated > 0 or archived > 0:
        await archive_recent_over_limit(db, instance=instance, trigger="admin_advanced_save")

    return {"created": created, "updated": updated, "archived": archived}


@ai_instance_router.post("/ai_instance/{instance_id}/save")
async def save_instance(
    instance_id: int,
    data: dict[str, object],  # Admin API: dynamic structure with runtime validation
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Save instance prompt_variables and dimensions."""
    # Get instance
    instance = await ai_instance_crud.get(db, record_id=instance_id)
    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")

    update_data: dict[str, object] = {}

    # Validate and update prompt_variables
    if "prompt_variables" in data:
        prompt_variables = data["prompt_variables"]
        if not isinstance(prompt_variables, dict):
            raise HTTPException(status_code=400, detail="prompt_variables must be a dict")
        update_data["prompt_variables"] = prompt_variables

    if "status" in data:
        status_value = _coerce_int(data.get("status"))
        if status_value is None:
            raise HTTPException(status_code=400, detail="status must be an integer")
        if status_value not in (int(AIInstanceStatus.ACTIVE), int(AIInstanceStatus.INACTIVE)):
            raise HTTPException(
                status_code=400,
                detail="status can only be Active or Inactive in advanced edit",
            )
        update_data["status"] = status_value

    # Validate and update dimensions (skip items with empty score/algorithm)
    updated_dims = 0
    created_dims = 0

    if "dimensions" in data:
        raw_dimensions = data["dimensions"]
        if not isinstance(raw_dimensions, list):
            raise HTTPException(status_code=400, detail="dimensions must be a list")

        cleaned_dimensions: list[JSONDict] = []

        for dim_data in raw_dimensions:
            if not isinstance(dim_data, dict):
                raise HTTPException(status_code=400, detail="Each dimension must be a dict")

            dimension_id = dim_data.get("dimension_id")
            parsed_dimension_id = _coerce_int(dimension_id)
            if parsed_dimension_id is None:
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
            parsed_algorithm = _coerce_int(algorithm)
            if parsed_algorithm not in {1, 2}:
                raise HTTPException(status_code=400, detail="Invalid algorithm")

            cleaned: JSONDict = {
                "dimension_id": parsed_dimension_id,
                "score": int(score),
                "position_mapping_algorithm": parsed_algorithm,
            }

            if parsed_algorithm == PositionMappingAlgorithm.V1.value:
                params = dim_data.get("position_mapping_params", {})
                if not isinstance(params, dict):
                    raise HTTPException(
                        status_code=400, detail="position_mapping_params must be a dict"
                    )
                try:
                    parsed_params = parse_algorithm_params(PositionMappingAlgorithm.V1, params)
                    cleaned["position_mapping_params"] = cast(JSONDict, parsed_params)
                except ValueError as exc:
                    raise HTTPException(status_code=400, detail=str(exc)) from exc

            cleaned_dimensions.append(cleaned)

        if cleaned_dimensions:
            # Batch update only when we have valid dimensions
            result = await update_dimensions_batch(
                db,
                instance_id=instance_id,
                dimensions_data=cleaned_dimensions,
                commit=False,
            )
            updated_dims = result["updated"]
            created_dims = result["created"]

    # Optional positions mapping from preview: { dimension_id: position }
    if "positions" in data and isinstance(data["positions"], dict):
        for key, val in data["positions"].items():
            try:
                dim_id = int(key)
                pv = _coerce_int(val)
                if pv is None:
                    continue
                if 0 <= pv <= POSITION_MAX_VALUE:
                    stmt = select(AIInstanceDimension).where(
                        AIInstanceDimension.instance_id == instance_id,
                        AIInstanceDimension.dimension_id == dim_id,
                    )
                    dim_result = await db.execute(stmt)
                    dimension_row = dim_result.scalar_one_or_none()
                    if dimension_row is not None:
                        dimension_row.position = pv
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
        relationship_id = _coerce_int(data["relationship_id"])
        if relationship_id is None:
            logger.error(
                "update_relationship_id_failed",
                instance_id=instance_id,
                error="invalid_id",
            )
        else:
            update_data["relationship_id"] = relationship_id

    if "typing_speed_wpm" in data:
        raw_value = data["typing_speed_wpm"]
        typing_speed = _coerce_int(raw_value)
        if typing_speed is None:
            raise HTTPException(status_code=400, detail="typing_speed_wpm must be an integer")
        if typing_speed <= 0:
            raise HTTPException(status_code=400, detail="typing_speed_wpm must be greater than 0")
        update_data["typing_speed_wpm"] = typing_speed

    if update_data:
        for field, value in update_data.items():
            setattr(instance, field, value)
        db.add(instance)

    memory_changes = _parse_memory_changes(data.get("memory_changes"))
    has_memory_changes = any(memory_changes[key] for key in ("create", "update", "archive_ids"))
    memory_result = {"created": 0, "updated": 0, "archived": 0}
    if has_memory_changes:
        locked_instance = await lock_instance_for_memory_write(db, instance_id)
        memory_result = await _apply_instance_memory_changes(
            db,
            instance=locked_instance,
            memory_changes=memory_changes,
        )

    await db.commit()

    logger.info(
        "instance_advanced_saved",
        instance_id=instance_id,
        updated_dimensions=updated_dims,
        created_dimensions=created_dims,
        memory_created=memory_result["created"],
        memory_updated=memory_result["updated"],
        memory_archived=memory_result["archived"],
    )

    return {
        "success": True,
        "message": "Saved successfully",
        "updated_dimensions": updated_dims,
        "created_dimensions": created_dims,
        "memory_result": memory_result,
    }


@ai_instance_router.post("/ai_instance/{instance_id}/generate-relationship")
async def generate_instance_relationship(
    instance_id: int,
    data: dict[str, object] | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Preview or persist generate-relationship using admin service (overrides + preview)."""
    try:
        overrides = None
        preview = True
        if isinstance(data, dict):
            raw_overrides = data.get("overrides")
            overrides = raw_overrides if isinstance(raw_overrides, dict) else None
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
