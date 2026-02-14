"""
AI instance creation service.

This module handles creating AI instances from personas/templates.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.ai import ai_instance
from app.enums import AIInstanceCreator
from app.models.ai import AIInstance
from app.models.ai.template import AIPersona, AITemplate
from app.schemas.ai import AIInstanceCreate
from app.services.ai.memory import copy_template_memories_to_instance
from app.services.ai.profile_integrity import ensure_instance_profile
from app.services.ai.relationship_scoring import (
    initialize_instance_relationship,
    initialize_relationship_scores,
)
from app.utils.logging import get_logger

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
