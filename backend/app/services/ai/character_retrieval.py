"""
AI character retrieval and validation module.

This module handles character information retrieval and validation
with clear error handling and single responsibility principle.
"""

from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from .queries import get_character_with_relations
from exceptions import AICharacterNotFoundError, AICharacterInactiveError
from utils.logging import get_logger

logger = get_logger(__name__)


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
