"""
AI relationship scoring query functions.

This module provides relationship scoring and evaluation query functions
with clear separation of concerns and pure function design.
"""

from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai import (
    AIDimension,
    AIDimensionRelationshipMapping,
    AIInstance,
    AIInstanceDimension,
    AIRelationship,
    AIStyleDimension,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)


async def get_instance_relationship_scores(
    db: AsyncSession, instance_id: int
) -> list[dict[str, Any]]:
    """
    Get relationship scores for an instance.

    Args:
        db: Database session
        instance_id: Instance ID

    Returns:
        List of score dictionaries
    """
    try:
        # Join with global AIDimension and style junction to get initial_position, name and display name
        result = await db.execute(
            select(
                AIInstanceDimension,
                AIStyleDimension.initial_position,
                AIDimension.name,
                AIDimension.display_name,
            )
            .join(AIDimension, AIInstanceDimension.dimension_id == AIDimension.id)
            .join(AIInstance, AIInstance.id == AIInstanceDimension.instance_id)
            .join(
                AIStyleDimension,
                and_(
                    AIStyleDimension.style_id == AIInstance.style_id,
                    AIStyleDimension.dimension_id == AIInstanceDimension.dimension_id,
                ),
            )
            .where(AIInstanceDimension.instance_id == instance_id)
            .order_by(AIDimension.name)
        )

        score_data = result.all()

        # Convert to dictionaries
        score_list = []
        for score, initial_position, dimension_name, dimension_display_name in score_data:
            score_list.append(
                {
                    "id": score.id,
                    "instance_id": score.instance_id,
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
            "instance_relationship_scores_retrieved",
            instance_id=instance_id,
            scores_count=len(score_list),
        )

        return score_list

    except Exception as e:
        logger.error(
            "instance_relationship_scores_query_failed",
            error=str(e),
            instance_id=instance_id,
        )
        return []


async def get_instance_current_relationship(db: AsyncSession, instance_id: int) -> dict[str, Any]:
    """
    Get the current relationship information for an instance.

    Args:
        db: Database session
        instance_id: Instance ID

    Returns:
        Dictionary containing current relationship info, or empty dict if not found
    """
    try:
        # Current relationship stored at instance level
        result = await db.execute(select(AIInstance).where(AIInstance.id == instance_id))
        instance = result.scalar_one_or_none()

        if instance and getattr(instance, "relationship_id", None) is not None:
            current_relationship = {
                "relationship_id": instance.relationship_id,
                "relationship_display_name": None,  # display name can be resolved by caller if needed
                "instance_id": instance_id,
            }

            logger.debug(
                "instance_current_relationship_retrieved",
                instance_id=instance_id,
                relationship_id=instance.relationship_id,
            )

            return current_relationship
        logger.debug("no_current_relationship_found", instance_id=instance_id)
        return {}

    except Exception as e:
        logger.error(
            "instance_current_relationship_query_failed",
            error=str(e),
            instance_id=instance_id,
        )
        return {}


async def get_relationship_score_ranges(db: AsyncSession, style_id: int) -> list[dict[str, Any]]:
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
            .join(
                AIRelationship, AIDimensionRelationshipMapping.relationship_id == AIRelationship.id
            )
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
                    "relationship_display_name": relationship.display_name,
                    "dimension_id": mapping.dimension_id,
                    "dimension_display_name": dimension_display_name,
                    "start_position": mapping.start_position,
                    "end_position": mapping.end_position,
                    "priority": mapping.priority,
                    "prompt_fragment": getattr(relationship, "prompt_fragment", ""),
                }
            )

        logger.debug(
            "relationship_score_ranges_retrieved", style_id=style_id, ranges_count=len(ranges)
        )

        return ranges

    except Exception as e:
        logger.error("relationship_score_ranges_query_failed", error=str(e), style_id=style_id)
        return []
