"""Admin AI Template API endpoints.

Handles template advanced-edit save for prompt variables, position mapping, and memories.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import verify_admin_session
from app.core.database import get_db
from app.crud.ai import ai_personality_placeholder as personality_placeholder_crud
from app.crud.ai import ai_template as ai_template_crud
from app.enums import AdminOperationType, AITemplateStatus, PositionMappingAlgorithm
from app.models.ai.memory import AITemplateMemory
from app.models.ai.personality import AIPersonality
from app.models.ai.template import AITemplate
from app.services.ai.global_unique_placeholder_keys import (
    GLOBAL_UNIQUE_PLACEHOLDER_KEYS_CONFIG_KEY,
    load_global_unique_placeholder_keys,
)
from app.services.ai.template_activation import get_missing_required_prompt_variables_for_template
from app.services.ai.utils.position_mapping import parse_algorithm_params
from app.utils.admin_logs import create_operation_log
from app.utils.logging import get_logger

logger = get_logger(__name__)

template_router = APIRouter()
MEMORY_IMPORTANCE_MIN = 1
MEMORY_IMPORTANCE_MAX = 10
CONFLICT_TEMPLATE_PREVIEW_LIMIT = 20
NORMALIZED_VALUE_PREVIEW_MAX = 200
GLOBAL_UNIQUE_CHECK_WARNING_CODE = "GLOBAL_UNIQUE_CHECK_SKIPPED"
GLOBAL_UNIQUE_CHECK_WARNING_MESSAGE = (
    "Global unique check was skipped due to invalid system configuration. "
    "Please check ai_global_unique_placeholder_keys."
)


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


def _coerce_bool(value: object, *, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    raise HTTPException(status_code=400, detail=f"{field_name} must be a boolean")


def _normalize_prompt_variable_value(value: object) -> str | None:
    if value is None:
        return None
    raw_value = value if isinstance(value, str) else str(value)
    normalized = raw_value.replace("\r\n", "\n").strip()
    if normalized == "":
        return None
    return normalized


def _build_normalized_preview(value: str) -> str:
    if len(value) <= NORMALIZED_VALUE_PREVIEW_MAX:
        return value
    return f"{value[:NORMALIZED_VALUE_PREVIEW_MAX]}..."


def _parse_admin_user_id(admin_user: dict[str, Any]) -> int:
    raw_admin_id = admin_user.get("id")
    if isinstance(raw_admin_id, bool):
        raise HTTPException(status_code=401, detail="Admin identity is invalid")
    if isinstance(raw_admin_id, int):
        admin_user_id = raw_admin_id
    elif isinstance(raw_admin_id, str) and raw_admin_id.strip().isdigit():
        admin_user_id = int(raw_admin_id.strip())
    else:
        raise HTTPException(status_code=401, detail="Admin identity is invalid")
    if admin_user_id <= 0:
        raise HTTPException(status_code=401, detail="Admin identity is invalid")
    return admin_user_id


def _build_global_unique_check_warning(*, reason: str) -> dict[str, str]:
    return {
        "code": GLOBAL_UNIQUE_CHECK_WARNING_CODE,
        "reason": reason,
        "message": GLOBAL_UNIQUE_CHECK_WARNING_MESSAGE,
    }


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


async def _get_global_unique_placeholder_keys(
    db: AsyncSession, *, personality_id: int
) -> tuple[list[str], bool]:
    config_keys, config_invalid = await load_global_unique_placeholder_keys(
        db,
        logger=logger,
        strict_item_type=True,
    )
    if config_invalid:
        return [], True
    if not config_keys:
        return [], False

    placeholders = await personality_placeholder_crud.get_placeholders_by_personality(
        db, personality_id=personality_id
    )
    personality_keys: set[str] = set()
    for placeholder in placeholders:
        key = str(getattr(placeholder, "placeholder_key", "") or "").strip()
        if not key:
            continue
        personality_keys.add(key)

    return [key for key in config_keys if key in personality_keys], False


async def _collect_global_unique_conflicts(
    db: AsyncSession,
    *,
    template_id: int,
    prompt_variables: object,
    placeholder_keys: list[str],
) -> list[dict[str, object]]:
    if not isinstance(prompt_variables, dict):
        return []

    normalized_targets: list[tuple[str, str]] = []
    for key in placeholder_keys:
        normalized_value = _normalize_prompt_variable_value(prompt_variables.get(key))
        if normalized_value is None:
            continue
        normalized_targets.append((key, normalized_value))
    if not normalized_targets:
        return []

    conflicts: list[dict[str, object]] = []
    for key, normalized_value in normalized_targets:
        db_normalized_value_expr = func.btrim(
            func.replace(
                func.coalesce(AITemplate.prompt_variables[key].astext, ""),
                "\r\n",
                "\n",
            )
        )

        count_stmt = (
            select(func.count(AITemplate.id))
            .join(AIPersonality, AIPersonality.id == AITemplate.personality_id)
            .where(
                AITemplate.id != template_id,
                AITemplate.prompt_variables.is_not(None),
                db_normalized_value_expr == normalized_value,
            )
        )
        duplicate_count = int((await db.execute(count_stmt)).scalar_one() or 0)
        if duplicate_count == 0:
            continue

        duplicate_stmt = (
            select(
                AITemplate.id.label("template_id"),
                AITemplate.display_name.label("template_display_name"),
                AITemplate.status.label("template_status"),
                AITemplate.personality_id.label("personality_id"),
                AIPersonality.display_name.label("personality_display_name"),
            )
            .join(AIPersonality, AIPersonality.id == AITemplate.personality_id)
            .where(
                AITemplate.id != template_id,
                AITemplate.prompt_variables.is_not(None),
                db_normalized_value_expr == normalized_value,
            )
            .order_by(AITemplate.id.asc())
            .limit(CONFLICT_TEMPLATE_PREVIEW_LIMIT)
        )
        duplicate_rows = (await db.execute(duplicate_stmt)).all()
        duplicate_templates: list[dict[str, object]] = []
        for row in duplicate_rows:
            duplicate_templates.append(
                {
                    "id": int(row.template_id),
                    "display_name": row.template_display_name,
                    "status": int(row.template_status),
                    "personality_id": int(row.personality_id),
                    "personality_display_name": row.personality_display_name,
                }
            )

        conflicts.append(
            {
                "placeholder_key": key,
                "normalized_value_preview": _build_normalized_preview(normalized_value),
                "duplicate_templates": duplicate_templates,
                "duplicate_count": duplicate_count,
            }
        )

    return conflicts


def _build_global_unique_conflict_response(
    conflicts: list[dict[str, object]],
) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={
            "detail": "Global unique Prompt Variables conflict",
            "requires_confirmation": True,
            "conflicts": conflicts,
        },
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


@template_router.post("/ai_template/{template_id}/save", response_model=None)
async def save_ai_template(
    template_id: int,
    data: dict[str, object],
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: dict[str, Any] = Depends(verify_admin_session),
) -> dict[str, object] | JSONResponse:
    """Save template advanced edit in one transaction."""
    template = await ai_template_crud.get(db, record_id=template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    admin_user_id = _parse_admin_user_id(admin_user)

    update_data: dict[str, object] = {}
    force_continue = _coerce_bool(data.get("force_continue", False), field_name="force_continue")
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

    effective_prompt_variables = (
        update_data.get("prompt_variables")
        if isinstance(update_data.get("prompt_variables"), dict)
        else template.prompt_variables
    )
    global_unique_check_warning: dict[str, str] | None = None
    conflicts: list[dict[str, object]] = []
    try:
        global_unique_placeholder_keys, config_invalid = await _get_global_unique_placeholder_keys(
            db, personality_id=int(template.personality_id)
        )
        if config_invalid:
            global_unique_check_warning = _build_global_unique_check_warning(
                reason="invalid_config"
            )
            logger.warning(
                "ai_template_global_unique_check_skipped_invalid_config",
                template_id=template_id,
                config_key=GLOBAL_UNIQUE_PLACEHOLDER_KEYS_CONFIG_KEY,
            )
        else:
            conflicts = await _collect_global_unique_conflicts(
                db,
                template_id=template_id,
                prompt_variables=effective_prompt_variables,
                placeholder_keys=global_unique_placeholder_keys,
            )
    except Exception as exc:
        global_unique_check_warning = _build_global_unique_check_warning(reason="check_failed")
        logger.error(
            "ai_template_global_unique_check_failed",
            template_id=template_id,
            error=str(exc),
            exc_info=True,
        )

    if conflicts and not force_continue:
        return _build_global_unique_conflict_response(conflicts)
    if conflicts and force_continue:
        logger.warning(
            "ai_template_global_unique_conflicts_force_continued",
            template_id=template_id,
            conflict_count=len(conflicts),
            conflict_keys=[str(conflict.get("placeholder_key")) for conflict in conflicts],
        )
        await create_operation_log(
            db=db,
            admin_user_id=admin_user_id,
            operation_type=int(AdminOperationType.UPDATE),
            resource_type="ai_template",
            resource_id=str(template_id),
            resource_name=str(getattr(template, "display_name", "") or ""),
            operation_desc="Force-continued global unique placeholder conflicts on template save",
            request=request,
            operation_meta={
                "action": "force_continue_global_unique_conflicts",
                "template_id": template_id,
                "conflict_count": len(conflicts),
                "conflicts": conflicts,
            },
            commit=False,
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

    response_payload: dict[str, object] = {
        "success": True,
        "message": "Data saved successfully",
        "memory_result": memory_result,
    }
    if global_unique_check_warning is not None:
        response_payload["warnings"] = [global_unique_check_warning]
    return response_payload
