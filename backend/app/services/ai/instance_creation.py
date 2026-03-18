"""
AI instance creation service.

This module handles creating AI instances from personas/templates.
"""

from collections.abc import Mapping
from typing import Any, cast

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.ai import ai_instance
from app.crud.profile import profile as profile_crud
from app.enums import AIInstanceCreator
from app.exceptions import AIRelationshipError
from app.models.ai import AIInstance
from app.models.ai.personality import AIPersonality
from app.models.ai.style import AIDimension, AIRelationship, AIStyleDimension
from app.models.ai.template import AIPersona, AITemplate
from app.models.base import generate_qiao_id
from app.models.user import User
from app.schemas.ai import AIInstanceCreate
from app.services.ai.memory import copy_template_memories_to_instance
from app.services.ai.profile_integrity import ensure_instance_profile
from app.services.ai.relationship_scoring import (
    initialize_instance_relationship,
    initialize_relationship_scores,
    update_instance_current_relationship,
)
from app.services.ai.response_schema import validate_style_personality_contract
from app.type_defs import JSONDict
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ManualAIInstanceCreateError(Exception):
    """Raised when manual AI instance creation fails with field-level errors."""

    def __init__(self, errors: dict[str, str]) -> None:
        super().__init__("Manual AI instance creation failed")
        self.errors = errors


def _normalize_optional_string(value: object) -> str | None:
    """Trim optional string inputs and collapse blanks to None."""
    if not isinstance(value, str):
        return None
    normalized_value = value.strip()
    return normalized_value or None


def _normalize_optional_json_dict(value: object) -> JSONDict | None:
    """Accept only JSON object payloads for manual instance inputs."""
    if isinstance(value, Mapping):
        return dict(value)
    return None


async def validate_instance_contract(
    db: AsyncSession,
    *,
    style_id: int | None,
    personality_id: int | None,
) -> str | None:
    """Validate style/personality score-schema contract before save."""
    if style_id is None or personality_id is None:
        return None

    style_result = await db.execute(
        select(AIDimension.name)
        .join(AIStyleDimension, AIStyleDimension.dimension_id == AIDimension.id)
        .where(AIStyleDimension.style_id == style_id)
        .order_by(AIDimension.name)
    )
    style_dimension_names = [row[0] for row in style_result.all() if isinstance(row[0], str)]
    if not style_dimension_names:
        return "Selected style has no dimensions"

    personality_result = await db.execute(
        select(AIPersonality.json_schema).where(AIPersonality.id == personality_id)
    )
    personality_schema = personality_result.scalar_one_or_none()
    if personality_schema is None:
        return "Selected personality not found"

    try:
        validate_style_personality_contract(style_dimension_names, personality_schema)
    except (TypeError, ValueError) as exc:
        return f"Style/personality contract mismatch: {exc!s}"
    return None


async def _validate_manual_instance_qiao_id(
    db: AsyncSession,
    *,
    qiao_id: str,
    user_id: int,
) -> None:
    """Validate that a manual instance qiao_id can own its own profile."""
    existing_instance = await ai_instance.get_by_qiao_id(db, qiao_id=qiao_id, user_id=user_id)
    if existing_instance is not None:
        raise ManualAIInstanceCreateError(
            {"qiao_id": "Qiao ID already exists for the selected user"}
        )

    profile_obj = await profile_crud.get_by_owner_qiao_id(db, owner_qiao_id=qiao_id)
    if profile_obj is not None:
        raise ManualAIInstanceCreateError(
            {"qiao_id": "Qiao ID is already bound to an existing persona or instance profile"}
        )


async def _get_relationship_display_name(
    db: AsyncSession,
    *,
    relationship_id: int,
) -> str:
    """Resolve relationship display_name for a manually selected relationship."""
    result = await db.execute(
        select(AIRelationship.display_name).where(AIRelationship.id == relationship_id)
    )
    display_name = result.scalar_one_or_none()
    if not isinstance(display_name, str) or not display_name:
        raise ManualAIInstanceCreateError({"relationship": "Selected relationship not found"})
    return display_name


async def _get_user_qiao_id(
    db: AsyncSession,
    *,
    user_id: int,
) -> str:
    """Resolve the owning user's qiao_id for manual instance creation."""
    result = await db.execute(select(User.qiao_id).where(User.id == user_id))
    user_qiao_id = result.scalar_one_or_none()
    if not isinstance(user_qiao_id, str) or not user_qiao_id:
        raise ManualAIInstanceCreateError({"user": "Owner User is required"})
    return user_qiao_id


async def create_manual_instance(
    db: AsyncSession,
    *,
    user_id: int | None,
    qiao_id: object,
    style_id: int | None,
    personality_id: int | None,
    relationship_id: int | None,
    request_params: object,
    llm_config_id: int | None,
    prompt_variables: object,
    relationship_counts: object,
    creation_metadata: object,
    status: int | None,
    typing_speed_wpm: object,
    timezone: object,
) -> AIInstance:
    """Create a manual AI instance in a single transaction."""
    errors: dict[str, str] = {}
    if user_id is None:
        errors["user"] = "Owner User is required"
    if style_id is None:
        errors["style"] = "AI Style is required"
    if personality_id is None:
        errors["personality"] = "AI Personality is required"
    if errors:
        raise ManualAIInstanceCreateError(errors)
    validated_user_id = cast(int, user_id)
    validated_user_qiao_id = await _get_user_qiao_id(db, user_id=validated_user_id)
    validated_style_id = cast(int, style_id)
    validated_personality_id = cast(int, personality_id)
    validated_relationship_id = relationship_id

    contract_error = await validate_instance_contract(
        db,
        style_id=validated_style_id,
        personality_id=validated_personality_id,
    )
    if contract_error is not None:
        raise ManualAIInstanceCreateError({"personality": contract_error})

    normalized_qiao_id = _normalize_optional_string(qiao_id) or generate_qiao_id()
    await _validate_manual_instance_qiao_id(
        db,
        qiao_id=normalized_qiao_id,
        user_id=validated_user_id,
    )

    metadata = _normalize_optional_json_dict(creation_metadata) or {}
    metadata["source"] = "admin_manual"

    try:
        instance_data = AIInstanceCreate(
            user_id=validated_user_id,
            user_qiao_id=validated_user_qiao_id,
            qiao_id=normalized_qiao_id,
            username=None,
            creation_metadata=metadata,
            style_id=validated_style_id,
            personality_id=validated_personality_id,
            placeholder_overrides=_normalize_optional_json_dict(prompt_variables),
            request_params=_normalize_optional_json_dict(request_params),
            llm_config_id=llm_config_id,
            relationship_id=None,
            relationship_counts=_normalize_optional_json_dict(relationship_counts),
            status=status if status is not None else 1,
            typing_speed_wpm=cast(Any, typing_speed_wpm),
            timezone=_normalize_optional_string(timezone) or "Asia/Shanghai",
            created_by=int(AIInstanceCreator.ADMIN),
        )
    except ValidationError as exc:
        validation_errors: dict[str, str] = {}
        for error in exc.errors():
            location = error.get("loc", ())
            field_name = str(location[0]) if location else "form"
            validation_errors[field_name] = str(error.get("msg", "Invalid value"))
        raise ManualAIInstanceCreateError(validation_errors) from exc

    try:
        instance = await ai_instance.create(db, obj_in=instance_data, commit=False)
        await ensure_instance_profile(
            db,
            instance=instance,
            source="instance_creation.create_manual_instance",
        )
    except (TypeError, ValueError) as exc:
        await db.rollback()
        logger.error(
            "manual_instance_profile_validation_failed",
            error=str(exc),
            user_id=user_id,
            instance_qiao_id=normalized_qiao_id,
        )
        raise ManualAIInstanceCreateError({"qiao_id": str(exc)}) from exc
    except Exception as exc:
        await db.rollback()
        logger.error(
            "manual_instance_creation_failed",
            error=str(exc),
            user_id=user_id,
            instance_qiao_id=normalized_qiao_id,
            exc_info=True,
        )
        raise

    try:
        await initialize_relationship_scores(db, instance.id, validated_style_id)
        if validated_relationship_id is None:
            await initialize_instance_relationship(db, instance_id=instance.id)
        else:
            relationship_display_name = await _get_relationship_display_name(
                db,
                relationship_id=validated_relationship_id,
            )
            updated = await update_instance_current_relationship(
                db,
                instance_id=instance.id,
                relationship_id=validated_relationship_id,
                relationship_display_name=relationship_display_name,
            )
            if not updated:
                raise ManualAIInstanceCreateError(
                    {"relationship": "Failed to persist the selected relationship"}
                )
        await db.commit()
    except AIRelationshipError as exc:
        await db.rollback()
        logger.error(
            "manual_instance_relationship_initialization_failed",
            error=str(exc),
            user_id=user_id,
            instance_qiao_id=normalized_qiao_id,
            exc_info=True,
        )
        raise ManualAIInstanceCreateError(
            {"relationship": "Failed to initialize relationship for new instance"}
        ) from exc
    except ManualAIInstanceCreateError:
        await db.rollback()
        raise
    except Exception as exc:
        await db.rollback()
        logger.error(
            "manual_instance_creation_commit_failed",
            error=str(exc),
            user_id=user_id,
            instance_qiao_id=normalized_qiao_id,
            exc_info=True,
        )
        raise

    await db.refresh(instance)
    logger.info(
        "manual_instance_created",
        instance_id=instance.id,
        user_id=user_id,
        instance_qiao_id=instance.qiao_id,
    )
    return instance


async def create_instance_from_persona(
    db: AsyncSession,
    *,
    persona: AIPersona,
    template: AITemplate,
    user_id: int,
    user_qiao_id: str,
    created_by: AIInstanceCreator = AIInstanceCreator.USER,
) -> AIInstance:
    """
    Instantiate a persona using the provided template for the given user.

    Args:
        db: Database session
        persona: Persona inventory row
        template: AI template to hydrate persona with
        user_id: Owning user ID
        user_qiao_id: Owning user qiao_id
        created_by: Creator type (defaults to USER)

    Returns:
        Newly created AI instance
    """

    def _type_display_name(entity: object) -> str | None:
        ai_type = getattr(entity, "ai_type", None)
        return getattr(ai_type, "display_name", None) if ai_type is not None else None

    creation_metadata = {
        "persona_id": persona.id,
        "persona_qiao_id": persona.qiao_id,
        "persona_type_id": persona.type_id,
        "persona_type_name": _type_display_name(persona),
        "template_id": template.id,
        "template_display_name": template.display_name,
        "template_type_id": template.type_id,
        "template_type_name": _type_display_name(template),
        "template_style_id": template.style_id,
        "template_personality_id": template.personality_id,
        "template_prompt_variables": template.prompt_variables,
        "template_request_params": template.request_params,
        "template_timezone": getattr(template, "timezone", "Asia/Shanghai"),
        "template_typing_speed_wpm": template.typing_speed_wpm,
        "template_position_mapping_config": template.position_mapping_config,
        "template_is_reusable": template.is_reusable,
        "template_priority": template.priority,
        "template_status": template.status,
    }

    instance_data = AIInstanceCreate(
        user_id=user_id,
        user_qiao_id=user_qiao_id,
        qiao_id=persona.qiao_id,
        username=persona.username,
        creation_metadata=creation_metadata,
        style_id=template.style_id,
        personality_id=template.personality_id,
        placeholder_overrides=template.prompt_variables,
        request_params=template.request_params,
        llm_config_id=template.llm_config_id,
        relationship_id=None,
        relationship_counts=None,
        status=1,
        typing_speed_wpm=template.typing_speed_wpm,
        timezone=getattr(template, "timezone", "Asia/Shanghai"),
        created_by=int(created_by),
    )

    instance = await ai_instance.create(db, obj_in=instance_data, commit=False)
    if instance.qiao_id != persona.qiao_id:
        logger.error(
            "instance_qiao_id_mismatch",
            instance_qiao_id=instance.qiao_id,
            persona_qiao_id=persona.qiao_id,
        )
        raise ValueError("Instance qiao_id must match persona qiao_id")
    if int(getattr(instance, "status", 1)) != 1:
        instance.status = 1
        await db.flush()

    await ensure_instance_profile(
        db,
        instance=instance,
        source="instance_creation.create_instance_from_persona",
    )

    logger.info(
        "instance_created_from_persona",
        instance_qiao_id=instance.qiao_id,
        persona_qiao_id=persona.qiao_id,
        template_id=template.id,
    )

    await initialize_relationship_scores(
        db,
        instance.id,
        template.style_id,
        template.position_mapping_config,
    )
    await initialize_instance_relationship(db, instance_id=instance.id)

    await copy_template_memories_to_instance(db, template_id=template.id, instance=instance)

    await _mark_inventory_consumed(db, persona, template)

    return instance


async def _mark_inventory_consumed(
    db: AsyncSession,
    persona: AIPersona,
    template: AITemplate,
) -> None:
    """Update persona/template inventory after instantiation."""

    try:
        if int(persona.is_reusable) == 0 and int(persona.status) == 1:
            persona.status = 3  # consumed

        if int(template.is_reusable) == 0 and int(template.status) == 1:
            template.status = 3

        db.add(persona)
        db.add(template)
        await db.flush()
    except Exception as exc:
        logger.error(
            "inventory_update_failed",
            error=str(exc),
            persona_id=persona.id,
            template_id=template.id,
        )
