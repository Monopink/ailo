"""
AI character-related query functions.

This module provides character-related read/query functions with clear
separation of concerns and pure function design.
"""

from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from models.ai import (
    AICharacter,
    AIPersonality,
    AIPersonalityPlaceholder,
    AIStyle,
    AIRelationship,
    AIRelationshipIndex,
    AIRelationshipDimension,
)
from models.profile import Profile
from utils.logging import get_logger

logger = get_logger(__name__)


async def get_character_with_relations(
    db: AsyncSession, character_qiao_id: str
) -> Optional[Dict[str, Any]]:
    """
    Get character with all related data (personality, style, profile).

    Args:
        db: Database session
        character_qiao_id: Character's qiao_id

    Returns:
        Dictionary containing character and related data, or None if not found
    """
    try:
        result = await db.execute(
            select(AICharacter, AIPersonality, AIStyle, Profile)
            .join(AIPersonality, AICharacter.personality_id == AIPersonality.id)
            .join(AIStyle, AICharacter.style_id == AIStyle.id)
            .join(
                Profile,
                and_(Profile.owner_qiao_id == AICharacter.qiao_id, Profile.owner_type == 2),  # AI type
            )
            .where(AICharacter.qiao_id == character_qiao_id)
        )

        row = result.first()
        if not row:
            logger.warning("character_not_found", character_qiao_id=character_qiao_id)
            return None

        character, personality, style, profile = row

        # Get dimensions for the style
        dimensions_result = await db.execute(
            select(AIRelationshipDimension)
            .where(AIRelationshipDimension.style_id == style.id)
            .order_by(AIRelationshipDimension.name)
        )
        dimensions = [
            {
                "id": dim.id,
                "name": dim.name,
                "display_name": dim.display_name,
                "initial_position": dim.initial_position,
            }
            for dim in dimensions_result.scalars().all()
        ]

        return {
            "character": character,
            "personality": personality,
            "style": style,
            "profile": profile,
            "dimensions": dimensions,
            "character_id": character.id,
            "personality_id": personality.id,
            "style_id": style.id,
        }

    except Exception as e:
        logger.error(
            "character_with_relations_query_failed", error=str(e), character_qiao_id=character_qiao_id
        )
        return None


async def get_personality_with_placeholders(
    db: AsyncSession, personality_id: int
) -> Optional[Dict[str, Any]]:
    """
    Get personality with its placeholders.

    Args:
        db: Database session
        personality_id: Personality ID

    Returns:
        Dictionary containing personality and placeholders, or None if not found
    """
    try:
        # Get personality
        personality_result = await db.execute(
            select(AIPersonality).where(AIPersonality.id == personality_id)
        )
        personality = personality_result.scalar_one_or_none()

        if not personality:
            logger.warning("personality_not_found", personality_id=personality_id)
            return None

        # Get placeholders
        placeholders_result = await db.execute(
            select(AIPersonalityPlaceholder).where(
                AIPersonalityPlaceholder.personality_id == personality_id
            )
        )
        placeholders = list(placeholders_result.scalars().all())

        logger.debug(
            "personality_with_placeholders_retrieved",
            personality_id=personality_id,
            placeholders_count=len(placeholders),
        )

        return {
            "personality": personality,
            "placeholders": placeholders,
        }

    except Exception as e:
        logger.error(
            "personality_with_placeholders_query_failed", error=str(e), personality_id=personality_id
        )
        return None


async def get_style_with_relationships(db: AsyncSession, style_id: int) -> Optional[Dict[str, Any]]:
    """
    Get style with relationship mappings.

    Args:
        db: Database session
        style_id: Style ID

    Returns:
        Dictionary containing style and relationships, or None if not found
    """
    try:
        # Get style
        style_result = await db.execute(select(AIStyle).where(AIStyle.id == style_id))
        style = style_result.scalar_one_or_none()

        if not style:
            logger.warning("style_not_found", style_id=style_id)
            return None

        # Get relationship indexes
        indexes_result = await db.execute(
            select(AIRelationshipIndex, AIRelationship)
            .join(AIRelationship, AIRelationshipIndex.relationship_id == AIRelationship.id)
            .where(AIRelationshipIndex.style_id == style_id)
            .order_by(AIRelationshipIndex.start_position)
        )

        relationships = []
        for index, relationship in indexes_result:
            relationships.append(
                {
                    "index": index,
                    "relationship": relationship,
                    "dimension_id": index.dimension_id,
                    "dimension_name": index.dimension_name,
                    "start_position": index.start_position,
                    "end_position": index.end_position,
                    "priority": index.priority,
                }
            )

        logger.debug(
            "style_with_relationships_retrieved", style_id=style_id, relationships_count=len(relationships)
        )

        return {
            "style": style,
            "relationships": relationships,
        }

    except Exception as e:
        logger.error("style_with_relationships_query_failed", error=str(e), style_id=style_id)
        return None


async def get_character_id_by_qiao_id(db: AsyncSession, character_qiao_id: str) -> Optional[int]:
    """
    Get character ID by qiao_id.

    Args:
        db: Database session
        character_qiao_id: Character's qiao_id

    Returns:
        Character ID or None if not found
    """
    try:
        result = await db.execute(select(AICharacter.id).where(AICharacter.qiao_id == character_qiao_id))

        character_id = result.scalar_one_or_none()

        if character_id is None:
            logger.warning("character_id_not_found", character_qiao_id=character_qiao_id)

        return character_id

    except Exception as e:
        logger.error("character_id_query_failed", error=str(e), character_qiao_id=character_qiao_id)
        return None


async def get_all_characters(db: AsyncSession) -> List[Dict[str, Any]]:
    """
    Get all active characters for admin interface.

    Args:
        db: Database session

    Returns:
        List of character dictionaries with basic information
    """
    try:
        result = await db.execute(
            select(AICharacter, Profile)
            .outerjoin(Profile, AICharacter.qiao_id == Profile.owner_qiao_id)
            .where(AICharacter.status == 1)  # active characters only
            .order_by(AICharacter.created_at.desc())
        )

        characters = []
        for character, profile in result.all():
            characters.append(
                {
                    "id": character.id,
                    "qiao_id": character.qiao_id,
                    "name": (profile.nickname if profile else None) or f"Character {character.qiao_id}",
                    "category": character.category,
                    "user_qiao_id": character.user_qiao_id,
                    "created_at": character.created_at.isoformat() if character.created_at else None,
                }
            )

        logger.debug(
            "all_characters_retrieved",
            count=len(characters),
        )

        return characters

    except Exception as e:
        logger.error(
            "all_characters_retrieval_failed",
            error=str(e),
        )
        return []
