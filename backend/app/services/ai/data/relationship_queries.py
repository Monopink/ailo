"""
AI relationship scoring query functions.

This module provides relationship scoring and evaluation query functions
with clear separation of concerns and pure function design.
"""

from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.ai import AIRelationshipScore
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
        result = await db.execute(
            select(AIRelationshipScore)
            .where(AIRelationshipScore.character_id == character_id)
            .order_by(AIRelationshipScore.score_order)
        )

        scores = result.scalars().all()

        # Convert to dictionaries
        score_list = []
        for score in scores:
            score_list.append(
                {
                    "id": score.id,
                    "character_id": score.character_id,
                    "score_order": score.score_order,
                    "score": score.score,
                    "score_start": score.score_start,
                    "score_end": score.score_end,
                    "score_position": score.score_position,
                    "score_offset_algorithm": score.score_offset_algorithm,
                    "score_offset_coefficient": score.score_offset_coefficient,
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
            .order_by(AIRelationshipIndex.score_start)
        )

        ranges = []
        for index, relationship in result:
            ranges.append(
                {
                    "relationship_id": relationship.id,
                    "relationship_name": relationship.name,
                    "score_order": index.score_order,
                    "score_start": index.score_start,
                    "score_end": index.score_end,
                    "prompt_fragment": getattr(relationship, "prompt_fragment", ""),
                }
            )

        logger.debug("relationship_score_ranges_retrieved", style_id=style_id, ranges_count=len(ranges))

        return ranges

    except Exception as e:
        logger.error("relationship_score_ranges_query_failed", error=str(e), style_id=style_id)
        return []
