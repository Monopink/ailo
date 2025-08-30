"""
AI relationship scoring and type determination module.

This module handles relationship score management and relationship type determination
based on AI style configurations and score positions.
"""

from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession

from .data import (
    get_character_relationship_scores,
    get_character_id_by_qiao_id,
    get_relationship_score_ranges,
    get_style_with_relationships,
)
from .data.mutations import update_relationship_scores
from exceptions import AIRelationshipError
from utils.logging import get_logger

logger = get_logger(__name__)


# Exception classes moved to exceptions/business.py for consistency


async def get_relationship_scores(
    db: AsyncSession, character_qiao_id: str
) -> Optional[List[Dict[str, Any]]]:
    """
    Get relationship scores for a character.

    Args:
        db: Database session
        character_qiao_id: Character's qiao_id

    Returns:
        List of score dictionaries, or None if not found
    """
    try:
        # Get character ID first
        character_id = await get_character_id_by_qiao_id(db, character_qiao_id)
        if not character_id:
            logger.warning("character_not_found_for_scores", character_qiao_id=character_qiao_id)
            return None

        scores = await get_character_relationship_scores(db, character_id)

        if not scores:
            logger.info(
                "no_relationship_scores_found",
                character_qiao_id=character_qiao_id,
            )
            return None

        logger.debug(
            "relationship_scores_retrieved",
            character_qiao_id=character_qiao_id,
            score_count=len(scores),
        )

        return scores

    except Exception as e:
        logger.error(
            "relationship_scores_retrieval_failed",
            error=str(e),
            character_qiao_id=character_qiao_id,
        )
        # Non-fatal error: return None and log error
        return None


async def determine_relationship_type(
    db: AsyncSession, character_info: Dict[str, Any], scores: Optional[List[Dict[str, Any]]]
) -> Optional[Dict[str, Any]]:
    """
    Determine relationship type based on character style and scores.

    Args:
        db: Database session
        character_info: Character information dictionary
        scores: List of relationship scores

    Returns:
        Dictionary containing relationship information, or None if not determined
    """
    try:
        style_id = character_info.get("style_id")
        if not style_id:
            logger.warning("no_style_id_in_character_info", character_info=character_info)
            return None

        # Get style with relationship mappings
        style_data = await get_style_with_relationships(db, style_id)
        if not style_data:
            logger.warning("style_not_found", style_id=style_id)
            return None

        relationship_mappings = style_data["relationship_mappings"]

        if not scores:
            # Use default relationship (first one with lowest priority)
            default_mapping = _get_default_relationship_mapping(relationship_mappings)
            if default_mapping:
                logger.info(
                    "using_default_relationship_for_new_character",
                    style_id=style_id,
                    relationship_id=default_mapping["relationship"].id,
                )
                return {
                    "relationship": default_mapping["relationship"],
                    "mapping": default_mapping,
                    "is_default": True,
                }
            else:
                logger.error(
                    "no_default_relationship_found",
                    style_id=style_id,
                    mappings_count=len(relationship_mappings),
                )
                raise AIRelationshipError(
                    operation="get_default_relationship",
                    reason="no_default_mapping",
                    message=f"No default relationship mapping found for style {style_id}. "
                    f"This indicates a configuration error in ai_relationship_indexs table.",
                )

        # Calculate score positions
        score_positions = _calculate_score_positions(scores)

        # Find matching relationship
        matching_relationship = _find_matching_relationship(score_positions, relationship_mappings)

        if matching_relationship:
            logger.debug(
                "relationship_type_determined",
                style_id=style_id,
                relationship_id=matching_relationship["relationship"].id,
                score_positions=score_positions,
            )
            return {
                "relationship": matching_relationship["relationship"],
                "mapping": matching_relationship,
                "score_positions": score_positions,
                "is_default": False,
            }
        else:
            # No matching relationship found - this indicates a configuration error
            logger.error(
                "no_matching_relationship_found",
                style_id=style_id,
                score_positions=score_positions,
                available_mappings=len(relationship_mappings),
            )
            raise AIRelationshipError(
                operation="find_matching_relationship",
                reason="no_matching_mapping",
                message=f"No relationship mapping found for style {style_id} with scores {score_positions}. "
                f"This indicates a configuration error in ai_relationship_indexs table.",
            )

    except Exception as e:
        logger.error(
            "relationship_type_determination_failed",
            error=str(e),
            character_info=character_info,
            scores=scores,
        )
        raise AIRelationshipError(
            operation="determine_relationship_type",
            reason="processing_failed",
            message=f"Failed to determine relationship type: {str(e)}",
        )


async def update_character_relationship_scores(
    db: AsyncSession, character_id: int, new_scores: Dict[int, int]
) -> bool:
    """
    Update relationship scores for a character.

    Args:
        db: Database session
        character_id: Character ID
        new_scores: Dictionary of score_order -> score_value

    Returns:
        True if successful, False otherwise
    """
    try:
        success = await update_relationship_scores(db, character_id, new_scores)

        if success:
            logger.debug(
                "relationship_scores_updated",
                character_id=character_id,
                scores=new_scores,
            )
        else:
            logger.warning(
                "relationship_scores_update_failed",
                character_id=character_id,
                scores=new_scores,
            )

        return success

    except Exception as e:
        logger.error(
            "character_relationship_scores_update_failed",
            error=str(e),
            character_id=character_id,
            scores=new_scores,
        )
        raise AIRelationshipError(
            operation="update_relationship_scores",
            reason="update_failed",
            message=f"Failed to update relationship scores: {str(e)}",
        )


def _calculate_score_positions(scores: List[Dict[str, Any]]) -> Dict[int, int]:
    """
    Calculate score positions as percentiles (0-1000).

    Args:
        scores: List of score dictionaries
        style: Style instance

    Returns:
        Dictionary mapping score_order to position
    """
    try:
        positions = {}

        for score in scores:
            score_order = score["score_order"]
            current_score = score["score"]
            score_start = score.get("score_start", 0)
            score_end = score.get("score_end", 1000)

            # Calculate position as percentile
            if score_end > score_start:
                position = int(((current_score - score_start) / (score_end - score_start)) * 1000)
                position = max(0, min(1000, position))  # Clamp to 0-1000
            else:
                position = 500  # Default middle position

            positions[score_order] = position

        logger.debug("score_positions_calculated", positions=positions)
        return positions

    except Exception as e:
        logger.error("score_position_calculation_failed", error=str(e), scores=scores)
        return {}


def _find_matching_relationship(
    score_positions: Dict[int, int], relationship_mappings: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """
    Find relationship mapping that matches the score positions.

    Args:
        score_positions: Dictionary of score_order -> position
        relationship_mappings: List of relationship mapping dictionaries

    Returns:
        Matching relationship mapping, or None if no match
    """
    try:
        # Sort mappings by priority (lower number = higher priority)
        sorted_mappings = sorted(relationship_mappings, key=lambda x: x.get("priority", 999))

        for mapping in sorted_mappings:
            score_order = mapping["score_order"]
            start_position = mapping["start_position"]
            end_position = mapping["end_position"]

            if score_order in score_positions:
                position = score_positions[score_order]

                # Check if position falls within range
                if start_position <= position <= end_position:
                    logger.debug(
                        "relationship_mapping_matched",
                        score_order=score_order,
                        position=position,
                        start_position=start_position,
                        end_position=end_position,
                        relationship_id=mapping["relationship"].id,
                    )
                    return mapping

        logger.debug("no_relationship_mapping_matched", score_positions=score_positions)
        return None

    except Exception as e:
        logger.error(
            "relationship_matching_failed",
            error=str(e),
            score_positions=score_positions,
            mappings_count=len(relationship_mappings),
        )
        return None


def _get_default_relationship_mapping(
    relationship_mappings: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Get default relationship mapping (first one with lowest priority).

    Args:
        relationship_mappings: List of relationship mapping dictionaries

    Returns:
        Default relationship mapping, or None if no mappings
    """
    try:
        if not relationship_mappings:
            return None

        # Sort by priority and return first one
        sorted_mappings = sorted(relationship_mappings, key=lambda x: x.get("priority", 999))
        default_mapping = sorted_mappings[0]

        logger.debug(
            "default_relationship_mapping_selected",
            relationship_id=default_mapping["relationship"].id,
            priority=default_mapping.get("priority", 999),
        )

        return default_mapping

    except Exception as e:
        logger.error("default_relationship_selection_failed", error=str(e))
        return None
