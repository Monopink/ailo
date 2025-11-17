"""
AI character creation service.

This module handles creating AI character instances from templates.
"""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from crud.ai import ai_character, ai_profile_template, ai_character_template
from crud.profile import profile as profile_crud
from models.ai import AICharacter
from schemas.ai import AICharacterCreate
from schemas.profile import ProfileCreate, ProfileUpdate
from enums import ProfileOwnerType
from utils.logging import get_logger

logger = get_logger(__name__)


async def create_character_from_template(
    db: AsyncSession, template_qiao_id: str, user_qiao_id: str, user_id: int
) -> AICharacter:
    """
    Create AI character instance from profile template.

    Args:
        db: Database session
        template_qiao_id: Profile template qiao_id
        user_qiao_id: Owner user qiao_id
        user_id: Owner user ID

    Returns:
        Created AI character

    Raises:
        ValueError: If template not found or invalid
    """
    # 1. Query profile template
    profile_template = await ai_profile_template.get_by_qiao_id(db, qiao_id=template_qiao_id)
    if not profile_template:
        logger.error("profile_template_not_found", template_qiao_id=template_qiao_id)
        raise ValueError("Profile template not found")

    if profile_template.status != 1:
        logger.error("profile_template_inactive", template_qiao_id=template_qiao_id)
        raise ValueError("Profile template is inactive")

    # 2. Query character template
    character_template = await ai_character_template.get(db, id=profile_template.character_template_id)
    if not character_template:
        logger.error(
            "character_template_not_found",
            character_template_id=profile_template.character_template_id,
        )
        raise ValueError("Character template not found")

    if character_template.status != 1:
        logger.error(
            "character_template_inactive",
            character_template_id=profile_template.character_template_id,
        )
        raise ValueError("Character template is inactive")

    # 3. Create AI character
    # Note: Keep AICharacterCreate aligned with current schema definitions.
    # - Use placeholder_overrides instead of prompt_variables
    # - Do not pass position_mapping_* here to avoid schema/DB type mismatch; rely on DB defaults
    character_data = AICharacterCreate(
        category=profile_template.category,
        style_id=character_template.style_id,
        personality_id=character_template.personality_id,
        memory=character_template.memory,
        placeholder_overrides=character_template.prompt_variables,
        # Persist source template for discovery de-duplication and audit trail
        created_from_profile_qiao_id=template_qiao_id,
        # Inherit request_params from character template (LLM parameter overrides)
        request_params=character_template.request_params,
        typing_speed_wpm=character_template.typing_speed_wpm,
        timezone=getattr(character_template, "timezone", "Asia/Shanghai"),
    )

    character = await ai_character.create(db, obj_in=character_data, commit=False)

    # Ensure ownership is set even if schema ignored extras
    try:
        if not getattr(character, "user_id", None):
            character.user_id = user_id
        if not getattr(character, "user_qiao_id", None):
            character.user_qiao_id = user_qiao_id
        # Set active status explicitly if model default differs
        if int(getattr(character, "status", 1)) != 1:
            character.status = 1
        await db.flush()
    except Exception as e:
        logger.error("character_post_create_update_failed", error=str(e))

    logger.info(
        "character_created_from_template",
        character_qiao_id=character.qiao_id,
        template_qiao_id=template_qiao_id,
        user_qiao_id=user_qiao_id,
    )

    # 3.1 Ensure AI profile exists or update from profile template (overwrite with latest values)
    try:
        # Trim helper to satisfy schema length constraints
        def _trim(value: Optional[str], max_len: int) -> Optional[str]:
            if value is None:
                return None
            return value[:max_len]

        nickname = _trim(profile_template.nickname, 10)
        avatar_url = _trim(profile_template.avatar_url, 500)
        bio = _trim(profile_template.bio, 70)
        region = _trim(profile_template.region, 100)
        gender = profile_template.gender

        existing = await profile_crud.get_by_owner(
            db, owner_id=character.id, owner_type=ProfileOwnerType.AI
        )
        if existing:
            logger.warning(
                "ai_profile_overwritten_from_template",
                character_qiao_id=character.qiao_id,
                template_qiao_id=template_qiao_id,
                profile_id=existing.id,
            )
            await profile_crud.update_by_owner(
                db,
                owner_id=character.id,
                owner_type=ProfileOwnerType.AI,
                obj_in=ProfileUpdate(
                    nickname=nickname,
                    gender=gender,
                    avatar_url=avatar_url,
                    avatar_prompt=None,
                    bio=bio,
                    region=region,
                ),
                commit=False,
            )
        else:
            await profile_crud.create_with_owner(
                db,
                obj_in=ProfileCreate(
                    nickname=nickname,
                    gender=gender,
                    avatar_url=avatar_url,
                    avatar_prompt=None,
                    bio=bio,
                    region=region,
                ),
                owner_id=character.id,
                owner_qiao_id=character.qiao_id,
                owner_type=ProfileOwnerType.AI,
                commit=False,
            )
    except Exception as e:
        # Non-fatal; character has been created. Log error for diagnostics.
        logger.error(
            "ai_profile_sync_from_template_failed",
            error=str(e),
            character_qiao_id=character.qiao_id,
            template_qiao_id=template_qiao_id,
        )

    # 4. Initialize relationship scores
    from services.ai.relationship_scoring import initialize_relationship_scores

    await initialize_relationship_scores(
        db,
        character.id,
        character_template.style_id,
        character_template.position_mapping_config,
    )

    # 5. Handle single-use template deactivation (no physical delete in MVP)
    try:
        # Deactivate non-reusable profile template
        if int(profile_template.is_reusable) == 0 and int(profile_template.status) == 1:
            profile_template.status = 2  # inactive
            logger.debug(
                "profile_template_deactivated",
                template_id=profile_template.id,
                template_qiao_id=profile_template.qiao_id,
            )

        # Deactivate non-reusable character template
        if int(character_template.is_reusable) == 0 and int(character_template.status) == 1:
            character_template.status = 2  # inactive
            logger.debug(
                "character_template_deactivated",
                character_template_id=character_template.id,
            )

        await db.flush()
    except Exception as e:
        # Non-fatal: log only, character already created
        logger.error(
            "template_deactivation_failed",
            error=str(e),
            template_qiao_id=template_qiao_id,
            user_qiao_id=user_qiao_id,
        )

    return character
