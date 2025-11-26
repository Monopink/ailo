"""
AI instance creation service.

This module handles creating AI instances from personas/templates.
"""

from typing import Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from crud.ai import ai_instance
from crud.profile import profile as profile_crud
from models.ai import AIInstance
from models.ai.template import AIPersona, AITemplate
from schemas.ai import AIInstanceCreate
from schemas.profile import ProfileCreate, ProfileUpdate
from enums import AIInstanceCreator, ProfileOwnerType
from utils.logging import get_logger

logger = get_logger(__name__)


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

    def _type_display_name(entity: Any) -> Optional[str]:
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
        "template_memory": template.memory,
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
        creation_metadata=creation_metadata,
        style_id=template.style_id,
        personality_id=template.personality_id,
        memory=template.memory,
        placeholder_overrides=template.prompt_variables,
        request_params=template.request_params,
        typing_speed_wpm=template.typing_speed_wpm,
        timezone=getattr(template, "timezone", "Asia/Shanghai"),
        created_by=int(created_by),
    )

    instance = await ai_instance.create(db, obj_in=instance_data, commit=False)
    if int(getattr(instance, "status", 1)) != 1:
        instance.status = 1
        await db.flush()

    logger.info(
        "instance_created_from_persona",
        instance_qiao_id=instance.qiao_id,
        persona_qiao_id=persona.qiao_id,
        template_id=template.id,
    )

    await _sync_profile_from_persona(db, instance, persona)

    # Initialize relationship scores
    from services.ai.relationship_scoring import initialize_relationship_scores

    await initialize_relationship_scores(
        db,
        instance.id,
        template.style_id,
        template.position_mapping_config,
    )

    await _mark_inventory_consumed(db, persona, template)

    return instance


async def _sync_profile_from_persona(
    db: AsyncSession,
    instance: AIInstance,
    persona: AIPersona,
) -> None:
    """Ensure each instance has a dedicated profile cloned from persona metadata."""

    try:
        persona_profile = await profile_crud.get_by_owner(
            db, owner_id=persona.id, owner_type=ProfileOwnerType.AI
        )

        if not persona_profile:
            logger.warning(
                "persona_profile_missing",
                persona_id=persona.id,
                persona_qiao_id=persona.qiao_id,
            )
            return

        def _trim(value: Optional[str], max_len: int) -> Optional[str]:
            if value is None:
                return None
            return value[:max_len]

        nickname = _trim(persona_profile.nickname, 10)
        avatar_url = _trim(persona_profile.avatar_url, 500)
        bio = _trim(persona_profile.bio, 70)
        region = _trim(persona_profile.region, 100)
        gender = persona_profile.gender

        existing = await profile_crud.get_by_owner(db, owner_id=instance.id, owner_type=ProfileOwnerType.AI)

        profile_payload = {
            "nickname": nickname,
            "gender": gender,
            "avatar_url": avatar_url,
            "avatar_prompt": getattr(persona_profile, "avatar_prompt", None),
            "bio": bio,
            "region": region,
        }

        if existing:
            await profile_crud.update_by_owner(
                db,
                owner_id=instance.id,
                owner_type=ProfileOwnerType.AI,
                obj_in=ProfileUpdate(**profile_payload),
                commit=False,
            )
        else:
            await profile_crud.create_with_owner(
                db,
                obj_in=ProfileCreate(**profile_payload),
                owner_id=instance.id,
                owner_qiao_id=instance.qiao_id,
                owner_type=ProfileOwnerType.AI,
                commit=False,
            )
    except Exception as exc:
        logger.error(
            "instance_profile_sync_failed",
            error=str(exc),
            instance_id=instance.id,
            persona_id=persona.id,
        )


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
