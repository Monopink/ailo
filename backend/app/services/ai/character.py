"""
AI character management module.

This module handles character information retrieval, validation, and management
with clear error handling and single responsibility principle.
"""

from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from .data import get_character_with_relations, get_profile_template_with_info, check_template_reusability
from .data.transactions import create_character_with_relations
from exceptions import AICharacterNotFoundError, AICharacterInactiveError, AICharacterCreationError
from utils.logging import get_logger

logger = get_logger(__name__)


# Exception classes moved to exceptions/business.py for consistency


async def get_character_info(db: AsyncSession, character_qiao_id: str) -> Dict[str, Any]:
    """
    Get character information with validation.

    Args:
        db: Database session
        character_qiao_id: Character's qiao_id

    Returns:
        Dictionary containing character information

    Raises:
        CharacterNotFoundError: If character doesn't exist
        CharacterInactiveError: If character is inactive or blocked
    """
    character_data = await get_character_with_relations(db, character_qiao_id)

    if not character_data:
        raise AICharacterNotFoundError(character_id=character_qiao_id)

    character = character_data["character"]

    # Validate character status
    if character.status != 1:  # 1 = active
        if character.status == 2:
            raise AICharacterInactiveError(
                character_id=character_qiao_id, status=character.status, message="Character is inactive"
            )
        elif character.status == 3:
            raise AICharacterInactiveError(
                character_id=character_qiao_id, status=character.status, message="Character is blocked"
            )
        else:
            raise AICharacterInactiveError(
                character_id=character_qiao_id,
                status=character.status,
                message=f"Character has invalid status {character.status}",
            )

    logger.debug(
        "character_info_retrieved",
        character_qiao_id=character_qiao_id,
        personality_id=character_data["personality_id"],
        style_id=character_data["style_id"],
    )

    return character_data


async def validate_character_status(character: Any) -> None:
    """
    Validate character status.

    Args:
        character: Character model instance

    Raises:
        CharacterInactiveError: If character is not active
    """
    if character.status != 1:  # 1 = active
        if character.status == 2:
            raise AICharacterInactiveError(
                character_id=character.qiao_id, status=character.status, message="Character is inactive"
            )
        elif character.status == 3:
            raise AICharacterInactiveError(
                character_id=character.qiao_id, status=character.status, message="Character is blocked"
            )
        else:
            raise AICharacterInactiveError(
                character_id=character.qiao_id,
                status=character.status,
                message=f"Character has invalid status {character.status}",
            )


async def get_character_configuration(db: AsyncSession, character_id: int) -> Dict[str, Any]:
    """
    Get character configuration including personality and style.

    Args:
        db: Database session
        character_id: Character ID

    Returns:
        Dictionary containing character configuration

    Raises:
        RuntimeError: If configuration retrieval fails
    """
    try:
        # This function needs to be implemented to get character configuration
        # For now, this is a placeholder implementation
        logger.debug("character_configuration_requested", character_id=character_id)

        return {
            "character_id": character_id,
            "personality": None,  # Would be populated with actual data
            "style": None,  # Would be populated with actual data
            "placeholders": {},
            "relationship_mappings": [],
        }

    except Exception as e:
        logger.error("character_configuration_failed", error=str(e), character_id=character_id)
        raise RuntimeError(f"Failed to get character configuration: {str(e)}")


async def create_character_from_template(db: AsyncSession, user_qiao_id: str, template_id: int) -> str:
    """
    Create character from template following the 9-step process.

    This implements the character creation flow from the prototype design:
    1. User selects ai_profile_template
    2. Find corresponding ai_info_template
    3. Write new information to ai_characters
    4. Write to profiles
    5. Write to contacts
    6. Delete ai_profile_templates if not reusable
    7. Delete ai_info_templates if not reusable
    8. Build new contact message
    9. Send message flow

    Args:
        db: Database session
        user_qiao_id: User's qiao_id
        template_id: Profile template ID

    Returns:
        Character qiao_id

    Raises:
        CharacterCreationError: If creation fails
    """
    try:
        # Step 1 & 2: Get profile template with info template
        template_data = await get_profile_template_with_info(db, template_id)

        if not template_data:
            raise AICharacterCreationError(
                template_id=str(template_id), reason="template_not_found", message="Template not found"
            )

        profile_template = template_data["profile_template"]
        info_template = template_data["info_template"]

        # Generate unique qiao_id for character
        from utils.snowflake import generate_snowflake_id

        character_qiao_id = f"qiao_{generate_snowflake_id()}"

        # Prepare character data
        character_data = {
            "qiao_id": character_qiao_id,
            "user_qiao_id": user_qiao_id,
            "category": profile_template.category,
            "status": 1,  # active
            "style_id": info_template.style_id,
            "personality_id": info_template.personality_id,
            "memory": info_template.memory,
            "prompt_variables": info_template.prompt_variables or {},
            "score_offset_algorithm": info_template.score_offset_algorithm,
            "score_offset_coefficient": info_template.score_offset_coefficient,
            "created_by": 1,  # user
            # Profile data
            "nickname": profile_template.nickname,
            "gender": profile_template.gender,
            "avatar_url": profile_template.avatar_url,
            "bio": profile_template.bio,
            "region": profile_template.region,
        }

        # Steps 3, 4, 5: Create character with relations
        created_character_qiao_id = await create_character_with_relations(db, character_data)

        # Steps 6 & 7: Clean up single-use templates
        reusability = await check_template_reusability(db, profile_template.id, info_template.id)
        await _cleanup_single_use_templates(db, profile_template, info_template, reusability)

        # Step 8: Build contact message
        contact_message = await _build_contact_message(profile_template)

        # Step 9: Send initial message (placeholder for now)
        await _send_initial_message(db, created_character_qiao_id, user_qiao_id, contact_message)

        logger.info(
            "character_created_from_template",
            character_qiao_id=created_character_qiao_id,
            user_qiao_id=user_qiao_id,
            template_id=template_id,
        )

        return created_character_qiao_id

    except Exception as e:
        logger.error(
            "character_creation_from_template_failed",
            error=str(e),
            user_qiao_id=user_qiao_id,
            template_id=template_id,
        )
        raise AICharacterCreationError(
            template_id=str(template_id),
            reason="creation_failed",
            message=f"Failed to create character from template: {str(e)}",
        )


async def _cleanup_single_use_templates(
    db: AsyncSession,
    profile_template: Any,
    info_template: Any,
    reusability: Dict[str, bool],
) -> None:
    """
    Clean up single-use templates after character creation.

    Args:
        db: Database session
        profile_template: Profile template object
        info_template: Info template object
        reusability: Template reusability status
    """
    try:
        cleanup_count = 0

        # Delete non-reusable profile template
        if not reusability["profile_reusable"]:
            await db.delete(profile_template)
            cleanup_count += 1
            logger.debug("profile_template_cleaned_up", template_id=profile_template.id)

        # Delete non-reusable info template
        if not reusability["info_reusable"]:
            await db.delete(info_template)
            cleanup_count += 1
            logger.debug("info_template_cleaned_up", template_id=info_template.id)

        if cleanup_count > 0:
            await db.flush()
            logger.debug("single_use_templates_cleaned_up", cleanup_count=cleanup_count)

    except Exception as e:
        logger.error("template_cleanup_failed", error=str(e))
        # Non-fatal error: log but don't raise


async def _build_contact_message(profile_template: Any) -> str:
    """
    Build initial contact message for new character.

    Args:
        profile_template: Profile template instance

    Returns:
        Contact message string
    """
    try:
        nickname = profile_template.nickname
        if not nickname:
            raise ValueError("Profile template nickname is required")

        message = f"你好！我是{nickname}，很高兴认识你！"

        logger.debug("contact_message_built", nickname=nickname, message_length=len(message))

        return message

    except Exception as e:
        logger.error("contact_message_build_failed", error=str(e))
        raise RuntimeError(f"Failed to build contact message: {str(e)}")


async def _send_initial_message(
    db: AsyncSession, character_qiao_id: str, user_qiao_id: str, message: str
) -> None:
    """
    Send initial message from new character.

    Args:
        db: Database session
        character_qiao_id: Character's qiao_id
        user_qiao_id: User's qiao_id
        message: Message content
    """
    try:
        # TODO: Integrate with message service to send initial message
        # This would call the message service to send the contact message

        logger.debug(
            "initial_message_prepared",
            character_qiao_id=character_qiao_id,
            user_qiao_id=user_qiao_id,
            message_length=len(message),
        )

        # For now, just log that the message would be sent
        logger.info(
            "initial_message_would_be_sent",
            character_qiao_id=character_qiao_id,
            user_qiao_id=user_qiao_id,
            message=message,
        )

    except Exception as e:
        logger.error(
            "initial_message_send_failed",
            error=str(e),
            character_qiao_id=character_qiao_id,
            user_qiao_id=user_qiao_id,
        )
        # Non-fatal error: log but don't raise since character is already created
