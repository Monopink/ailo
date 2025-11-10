"""
AI relationship scoring query functions.

This module provides relationship scoring and evaluation query functions
with clear separation of concerns and pure function design.
"""

from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from models.ai import (
    AICharacterDimension,
    AIStyleDimension,
    AIDimension,
    AICharacter,
    AIDimensionRelationshipMapping,
    AIRelationship,
)
from utils.logging import get_logger

logger = get_logger(__name__)


async def get_character_relationship_scores(db: AsyncSession, character_id: int) -> List[Dict[str, Any]]:
    """
    Get relationship scores for a character.

    Args:
        db: Database session
        character_id: Character ID

    Returns:
        List of score dictionaries
    """
    try:
        # Join with global AIDimension and style junction to get initial_position, name and display name
        result = await db.execute(
            select(
                AICharacterDimension,
                AIStyleDimension.initial_position,
                AIDimension.name,
                AIDimension.display_name,
            )
            .join(AIDimension, AICharacterDimension.dimension_id == AIDimension.id)
            .join(AICharacter, AICharacter.id == AICharacterDimension.character_id)
            .join(
                AIStyleDimension,
                and_(
                    AIStyleDimension.style_id == AICharacter.style_id,
                    AIStyleDimension.dimension_id == AICharacterDimension.dimension_id,
                ),
            )
            .where(AICharacterDimension.character_id == character_id)
            .order_by(AIDimension.name)
        )

        score_data = result.all()

        # Convert to dictionaries
        score_list = []
        for score, initial_position, dimension_name, dimension_display_name in score_data:
            score_list.append(
                {
                    "id": score.id,
                    "character_id": score.character_id,
                    "dimension_id": score.dimension_id,
                    "dimension_name": dimension_name,
                    "dimension_display_name": dimension_display_name,
                    "score": score.score,
                    "position": score.position,
                    "initial_position": initial_position,  # Add initial_position from dimension
                    "created_at": score.created_at,
                    "updated_at": score.updated_at,
                }
            )

        logger.debug(
            "character_relationship_scores_retrieved",
            character_id=character_id,
            scores_count=len(score_list),
        )

        return score_list

    except Exception as e:
        logger.error(
            "character_relationship_scores_query_failed",
            error=str(e),
            character_id=character_id,
        )
        return []


async def get_character_current_relationship(db: AsyncSession, character_id: int) -> Dict[str, Any]:
    """
    Get the current relationship information for a character.

    Args:
        db: Database session
        character_id: Character ID

    Returns:
        Dictionary containing current relationship info, or empty dict if not found
    """
    try:
        from models.ai import AICharacter

        # Current relationship stored at character level
        result = await db.execute(select(AICharacter).where(AICharacter.id == character_id))
        character = result.scalar_one_or_none()

        if character and getattr(character, "relationship_id", None) is not None:
            current_relationship = {
                "relationship_id": character.relationship_id,
                "relationship_display_name": None,  # display name can be resolved by caller if needed
                "character_id": character_id,
            }

            logger.debug(
                "character_current_relationship_retrieved",
                character_id=character_id,
                relationship_id=character.relationship_id,
            )

            return current_relationship
        else:
            logger.debug("no_current_relationship_found", character_id=character_id)
            return {}

    except Exception as e:
        logger.error(
            "character_current_relationship_query_failed",
            error=str(e),
            character_id=character_id,
        )
        return {}


async def get_relationship_score_ranges(db: AsyncSession, style_id: int) -> List[Dict[str, Any]]:
    """
    Get relationship score ranges for a style.

    Args:
        db: Database session
        style_id: Style ID

    Returns:
        List of score range dictionaries
    """
    try:
        result = await db.execute(
            select(
                AIDimensionRelationshipMapping,
                AIRelationship,
                AIDimension.display_name,
            )
            .join(AIRelationship, AIDimensionRelationshipMapping.relationship_id == AIRelationship.id)
            .join(AIDimension, AIDimensionRelationshipMapping.dimension_id == AIDimension.id)
            .join(
                AIStyleDimension,
                AIStyleDimension.dimension_id == AIDimensionRelationshipMapping.dimension_id,
            )
            .where(AIStyleDimension.style_id == style_id)
            .order_by(AIDimensionRelationshipMapping.start_position)
        )

        ranges = []
        for mapping, relationship, dimension_display_name in result:
            ranges.append(
                {
                    "relationship_id": relationship.id,
                    "relationship_name": relationship.name,
                    "dimension_id": mapping.dimension_id,
                    "dimension_display_name": dimension_display_name,
                    "start_position": mapping.start_position,
                    "end_position": mapping.end_position,
                    "priority": mapping.priority,
                    "prompt_fragment": getattr(relationship, "prompt_fragment", ""),
                }
            )

        logger.debug("relationship_score_ranges_retrieved", style_id=style_id, ranges_count=len(ranges))

        return ranges

    except Exception as e:
        logger.error("relationship_score_ranges_query_failed", error=str(e), style_id=style_id)
        return []
