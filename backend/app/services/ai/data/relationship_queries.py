"""
AI relationship scoring query functions.

This module provides relationship scoring and evaluation query functions
with clear separation of concerns and pure function design.
"""

from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.ai import AIRelationshipScore, AIRelationshipDimension
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
        # Join with AIRelationshipDimension to get initial_position
        result = await db.execute(
            select(AIRelationshipScore, AIRelationshipDimension.initial_position)
            .join(AIRelationshipDimension, AIRelationshipScore.dimension_id == AIRelationshipDimension.id)
            .where(AIRelationshipScore.character_id == character_id)
            .order_by(AIRelationshipScore.dimension_name)
        )

        score_data = result.all()

        # Convert to dictionaries
        score_list = []
        for score, initial_position in score_data:
            score_list.append(
                {
                    "id": score.id,
                    "character_id": score.character_id,
                    "dimension_id": score.dimension_id,
                    "dimension_name": score.dimension_name,
                    "score": score.score,
                    "position": score.position,
                    "initial_position": initial_position,  # Add initial_position from dimension
                    "relationship_id": score.relationship_id,
                    "relationship_display_name": score.relationship_display_name,
                    "relationship_counts": score.relationship_counts,
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
        # Get the first relationship score entry to determine current relationship
        result = await db.execute(
            select(AIRelationshipScore)
            .where(AIRelationshipScore.character_id == character_id)
            .where(AIRelationshipScore.relationship_id.isnot(None))
            .limit(1)
        )

        score = result.scalar_one_or_none()

        if score:
            current_relationship = {
                "relationship_id": score.relationship_id,
                "relationship_display_name": score.relationship_display_name,
                "character_id": character_id,
            }

            logger.debug(
                "character_current_relationship_retrieved",
                character_id=character_id,
                relationship_id=score.relationship_id,
                relationship_name=score.relationship_display_name,
            )

            return current_relationship
        else:
            logger.debug(
                "no_current_relationship_found",
                character_id=character_id,
            )
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
        from models.ai import AIRelationshipIndex, AIRelationship

        result = await db.execute(
            select(AIRelationshipIndex, AIRelationship)
            .join(AIRelationship, AIRelationshipIndex.relationship_id == AIRelationship.id)
            .where(AIRelationshipIndex.style_id == style_id)
            .order_by(AIRelationshipIndex.start_position)
        )

        ranges = []
        for index, relationship in result:
            ranges.append(
                {
                    "relationship_id": relationship.id,
                    "relationship_name": relationship.name,
                    "dimension_id": index.dimension_id,
                    "dimension_name": index.dimension_name,
                    "start_position": index.start_position,
                    "end_position": index.end_position,
                    "priority": index.priority,
                    "prompt_fragment": getattr(relationship, "prompt_fragment", ""),
                }
            )

        logger.debug("relationship_score_ranges_retrieved", style_id=style_id, ranges_count=len(ranges))

        return ranges

    except Exception as e:
        logger.error("relationship_score_ranges_query_failed", error=str(e), style_id=style_id)
        return []
