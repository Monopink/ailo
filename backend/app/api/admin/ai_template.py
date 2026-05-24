"""Admin AI Template API endpoints.

Handles template advanced-edit save for prompt variables, position mapping, and memories.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.crud.ai import ai_template as ai_template_crud
from app.enums import AITemplateStatus, PositionMappingAlgorithm
from app.models.ai.memory import AITemplateMemory
from app.services.ai.template_activation import get_missing_required_prompt_variables_for_template
from app.services.ai.utils.position_mapping import parse_algorithm_params
from app.utils.logging import get_logger

logger = get_logger(__name__)

template_router = APIRouter()
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


def _format_missing_prompt_variables_error(missing_keys: list[str]) -> str:
    return (
        f"Cannot activate template: missing required Prompt Variables ({', '.join(missing_keys)})"
    )


def _validate_template_memory_payload(payload: object) -> tuple[str, int, int, str]:
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

    display_order = _coerce_int(payload_dict.get("display_order"))
    if display_order is None:
        raise HTTPException(status_code=400, detail="display_order must be an integer")

    content = _coerce_text(payload_dict.get("content"))
    if content is None:
        raise HTTPException(status_code=400, detail="content is required")

    return memory_type, importance, display_order, content


async def _apply_template_memory_changes(
    db: AsyncSession,
    *,
    template_id: int,
    memory_changes: dict[str, list[object]],
) -> dict[str, int]:
    created = 0
    updated = 0
    archived = 0

    create_items = memory_changes["create"]
    update_items = memory_changes["update"]
    archive_ids_raw = memory_changes["archive_ids"]

    for item in create_items:
        memory_type, importance, display_order, content = _validate_template_memory_payload(item)
        db.add(
            AITemplateMemory(
                template_id=template_id,
                memory_type=memory_type,
                importance=importance,
                display_order=display_order,
                content=content,
            )
        )
        created += 1

    for item in update_items:
        if not isinstance(item, dict):
            raise HTTPException(status_code=400, detail="Invalid memory update payload")
        memory_id = _coerce_int(item.get("id"))
        if memory_id is None:
            raise HTTPException(status_code=400, detail="memory update id is required")
        stmt = select(AITemplateMemory).where(
            AITemplateMemory.id == memory_id,
            AITemplateMemory.template_id == template_id,
        )
        result = await db.execute(stmt)
        memory = result.scalar_one_or_none()
        if memory is None:
            raise HTTPException(status_code=404, detail=f"Template memory not found: {memory_id}")

        memory_type, importance, display_order, content = _validate_template_memory_payload(item)
        memory.memory_type = memory_type
        memory.importance = importance
        memory.display_order = display_order
        memory.content = content
        updated += 1

    archive_ids: list[int] = []
    for raw_id in archive_ids_raw:
        parsed_id = _coerce_int(raw_id)
        if parsed_id is None:
            raise HTTPException(status_code=400, detail="archive_ids must contain valid integers")
        archive_ids.append(parsed_id)
    if archive_ids:
        stmt = select(AITemplateMemory).where(
            AITemplateMemory.template_id == template_id,
            AITemplateMemory.id.in_(archive_ids),
        )
        result = await db.execute(stmt)
        memories = list(result.scalars().all())
        existing_ids = {int(memory.id) for memory in memories}
        missing = sorted(set(archive_ids) - existing_ids)
        if missing:
            raise HTTPException(status_code=404, detail=f"Template memories not found: {missing}")
        for memory in memories:
            await db.delete(memory)
            archived += 1

    return {"created": created, "updated": updated, "archived": archived}


@template_router.post("/ai_template/{template_id}/save")
async def save_ai_template(
    template_id: int, data: dict[str, object], db: AsyncSession = Depends(get_db)
) -> dict[str, object]:
    """Save template advanced edit in one transaction."""
    template = await ai_template_crud.get(db, record_id=template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    update_data: dict[str, object] = {}
    raw_status = data.get("status")
    next_status = int(getattr(template, "status", AITemplateStatus.INACTIVE))

    if "status" in data:
        status_value = _coerce_int(raw_status)
        if status_value is None:
            raise HTTPException(status_code=400, detail="status must be an integer")
        if status_value not in (int(AITemplateStatus.ACTIVE), int(AITemplateStatus.INACTIVE)):
            raise HTTPException(
                status_code=400,
                detail="status can only be Active or Inactive in advanced edit",
            )
        next_status = status_value
        update_data["status"] = next_status

    # Handle prompt_variables
    if "prompt_variables" in data:
        prompt_variables = data["prompt_variables"]
        if not isinstance(prompt_variables, dict):
            raise HTTPException(status_code=400, detail="prompt_variables must be a dict")
        update_data["prompt_variables"] = prompt_variables

    if "typing_speed_wpm" in data:
        raw_value = data["typing_speed_wpm"]
        typing_speed = _coerce_int(raw_value)
        if typing_speed is None:
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

    current_status = int(getattr(template, "status", AITemplateStatus.INACTIVE))
    is_transition_to_active = (
        "status" in data
        and next_status == int(AITemplateStatus.ACTIVE)
        and current_status != int(AITemplateStatus.ACTIVE)
    )
    if is_transition_to_active:
        effective_prompt_variables = (
            update_data.get("prompt_variables")
            if isinstance(update_data.get("prompt_variables"), dict)
            else template.prompt_variables
        )
        missing_keys = await get_missing_required_prompt_variables_for_template(
            db,
            personality_id=template.personality_id,
            prompt_variables=effective_prompt_variables,
        )
        if missing_keys:
            raise HTTPException(
                status_code=400,
                detail=_format_missing_prompt_variables_error(missing_keys),
            )

    memory_changes = _parse_memory_changes(data.get("memory_changes"))
    has_memory_changes = any(memory_changes[key] for key in ("create", "update", "archive_ids"))

    if not update_data and not has_memory_changes:
        raise HTTPException(status_code=400, detail="No data to update")

    for field, value in update_data.items():
        setattr(template, field, value)
    db.add(template)

    memory_result = {"created": 0, "updated": 0, "archived": 0}
    if has_memory_changes:
        memory_result = await _apply_template_memory_changes(
            db,
            template_id=template_id,
            memory_changes=memory_changes,
        )

    await db.commit()

    logger.info(
        "ai_template_advanced_saved",
        template_id=template_id,
        fields=list(update_data.keys()),
        memory_created=memory_result["created"],
        memory_updated=memory_result["updated"],
        memory_archived=memory_result["archived"],
    )

    return {
        "success": True,
        "message": "Data saved successfully",
        "memory_result": memory_result,
    }
