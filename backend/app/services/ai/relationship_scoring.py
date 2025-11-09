"""
AI relationship scoring and type determination module.

This module handles relationship score management and relationship type determination
based on AI style configurations and score positions.
"""

from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .data import (
    get_character_relationship_scores,
    get_character_id_by_qiao_id,
    get_style_with_relationships,
)
from .data.mutations import update_relationship_scores, set_current_relationship
from exceptions import AIRelationshipError
from utils.logging import get_logger

logger = get_logger(__name__)


# Exception classes moved to exceptions/business.py for consistency


async def get_relationship_scores(
    db: AsyncSession, character_qiao_id: str, auto_initialize: bool = True
) -> Optional[List[Dict[str, Any]]]:
    """
    Get relationship scores for a character.
    Auto-initialize scores based on initial_position if missing.

    Args:
        db: Database session
        character_qiao_id: Character's qiao_id
        auto_initialize: Whether to auto-initialize scores if missing (default: True)

    Returns:
        List of score dictionaries, or None if not found
    """
    try:
        character_id = await get_character_id_by_qiao_id(db, character_qiao_id)
        if not character_id:
            logger.warning("character_not_found_for_scores", character_qiao_id=character_qiao_id)
            return None

        scores = await get_character_relationship_scores(db, character_id)

        if not scores and auto_initialize:
            style_id = await _get_character_style_id(db, character_id)
            if not style_id:
                logger.error(
                    "character_style_missing_for_score_init",
                    character_qiao_id=character_qiao_id,
                    character_id=character_id,
                )
            else:
                try:
                    await initialize_relationship_scores(db, character_id, style_id)
                    scores = await get_character_relationship_scores(db, character_id)
                    if scores:
                        logger.info(
                            "relationship_scores_auto_initialized",
                            character_qiao_id=character_qiao_id,
                            style_id=style_id,
                        )
                except AIRelationshipError as init_error:
                    logger.error(
                        "relationship_score_autoinit_failed",
                        error=str(init_error),
                        character_qiao_id=character_qiao_id,
                        character_id=character_id,
                    )
                    return None

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


async def _get_character_style_id(db: AsyncSession, character_id: int) -> Optional[int]:
    """
    Fetch the style_id for a given character.
    """
    from models.ai import AICharacter

    try:
        result = await db.execute(select(AICharacter.style_id).where(AICharacter.id == character_id))
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(
            "character_style_lookup_failed",
            error=str(e),
            character_id=character_id,
        )
        return None


async def initialize_relationship_scores(
    db: AsyncSession, character_id: int, style_id: int, position_mapping_config: Optional[Dict[str, Any]] = None
) -> None:
    """
    Initialize relationship scores based on dimension initial_position.

    Args:
        db: Database session
        character_id: Character ID
        style_id: Style ID
        position_mapping_config: Per-dimension position mapping configuration from template

    Returns:
        None (scores are created and committed to database)

    Raises:
        AIRelationshipError: If initialization fails
    """
    try:
        from models.ai.character_dimension import AICharacterDimension
        from models.ai.style import AIStyleDimension

        # Get all dimensions for this style
        stmt = select(AIStyleDimension).where(AIStyleDimension.style_id == style_id)
        result = await db.execute(stmt)
        dimensions = result.scalars().all()

        if not dimensions:
            raise AIRelationshipError(
                operation="initialize_relationship_scores",
                reason="dimensions_not_found",
                message=f"No dimensions found for style {style_id}",
            )

        # Get position mapping config from template
        offset_config = position_mapping_config or {}

        # Create dimension records
        for dimension in dimensions:
            # Get offset config for this dimension
            dim_config = offset_config.get(dimension.name, {})
            algorithm = dim_config.get("algorithm", 1)
            params = dim_config.get("params", {})

            dimension_record = AICharacterDimension(
                character_id=character_id,
                dimension_id=dimension.id,
                score=dimension.initial_position,
                position=dimension.initial_position,
                position_mapping_algorithm=algorithm,
                position_mapping_params=params,
            )
            db.add(dimension_record)

        await db.commit()

        logger.info(
            "relationship_scores_initialized",
            character_id=character_id,
            scores_count=len(dimensions),
        )

    except AIRelationshipError:
        raise
    except Exception as e:
        logger.error(
            "relationship_scores_initialization_failed",
            error=str(e),
            character_id=character_id,
            exc_info=True,
        )
        raise AIRelationshipError(
            operation="initialize_relationship_scores",
            reason="initialization_failed",
            message=f"Failed to initialize relationship scores: {str(e)}",
        )


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

        # Unified key name for relationships collection
        relationships = style_data["relationships"]

        if not scores:
            # No scores available => per spec return empty relationship and log error
            logger.error(
                "no_scores_for_relationship_selection",
                style_id=style_id,
            )
            return None

        # Calculate score positions
        score_positions = _calculate_score_positions(scores)

        # Get current relationship ID from scores (if any)
        current_relationship_id = None
        try:
            character = character_info.get("character")
            if character is not None:
                current_relationship_id = getattr(character, "relationship_id", None)
        except Exception:
            current_relationship_id = None

        # Find matching relationship with current relationship priority and limit_count
        relationship_counts = {}
        try:
            if character is not None and getattr(character, "relationship_counts", None):
                relationship_counts = getattr(character, "relationship_counts") or {}
        except Exception:
            relationship_counts = {}

        matching_relationship = _find_matching_relationship(
            score_positions, relationships, current_relationship_id, relationship_counts
        )

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
            # No matching relationship found => return empty per spec
            logger.error(
                "no_matching_relationship_found",
                style_id=style_id,
                score_positions=score_positions,
                available_mappings=len(relationships),
            )
            return None

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


async def update_current_relationship(
    db: AsyncSession, character_id: int, relationship_id: int, relationship_display_name: str
) -> bool:
    """Persist the selected current relationship across all score rows for a character."""
    try:
        success = await set_current_relationship(
            db,
            character_id=character_id,
            relationship_id=relationship_id,
            relationship_display_name=relationship_display_name,
        )

        if success:
            logger.debug(
                "current_relationship_persisted",
                character_id=character_id,
                relationship_id=relationship_id,
                relationship_display_name=relationship_display_name,
            )
        else:
            logger.warning(
                "current_relationship_persist_failed",
                character_id=character_id,
                relationship_id=relationship_id,
            )

        return success

    except Exception as e:
        logger.error(
            "update_current_relationship_failed",
            error=str(e),
            character_id=character_id,
            relationship_id=relationship_id,
        )
        raise AIRelationshipError(
            operation="update_current_relationship",
            reason="update_failed",
            message=f"Failed to update current relationship: {str(e)}",
        )


def _calculate_score_positions(scores: List[Dict[str, Any]]) -> Dict[int, int]:
    """
    Calculate score positions as percentiles (0-1000).

    Args:
        scores: List of score dictionaries
        style: Style instance

    Returns:
        Dictionary mapping dimension_name to position
    """
    try:
        positions = {}

        for score in scores:
            dimension_name = score["dimension_name"]
            # Position is already calculated and stored in the database
            position = score.get("position", 500)  # Default middle position if not found
            positions[dimension_name] = position

        logger.debug("score_positions_calculated", positions=positions)
        return positions

    except Exception as e:
        logger.error("score_position_calculation_failed", error=str(e), scores=scores)
        return {}


def _find_matching_relationship(
    score_positions: Dict[int, int],
    relationship_mappings: List[Dict[str, Any]],
    current_relationship_id: Optional[int] = None,
    relationship_counts: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Find relationship mapping that matches the score positions.

    Implements per-dimension current relationship filtering: within each dimension,
    if current relationship is among candidates, filter out other relationships.

    Args:
        score_positions: Dictionary of dimension_name -> position
        relationship_mappings: List of relationship mapping dictionaries
        current_relationship_id: Current relationship ID for per-dimension filtering
        relationship_counts: Character-level relationship counts for limit_count enforcement

    Returns:
        Matching relationship mapping, or None if no match
    """
    try:
        # Group matching mappings by dimension
        dimension_matches: Dict[str, List[Dict[str, Any]]] = {}

        for mapping in relationship_mappings:
            dimension_name = mapping["dimension_name"]
            start_position = mapping["start_position"]
            end_position = mapping["end_position"]

            if dimension_name in score_positions:
                position = score_positions[dimension_name]

                # Check if position falls within range
                if start_position <= position <= end_position:
                    if dimension_name not in dimension_matches:
                        dimension_matches[dimension_name] = []
                    dimension_matches[dimension_name].append(mapping)
                    logger.debug(
                        "relationship_mapping_candidate",
                        dimension_name=dimension_name,
                        position=position,
                        start_position=start_position,
                        end_position=end_position,
                        relationship_id=mapping["relationship"].id,
                    )

        if not dimension_matches:
            logger.debug("no_relationship_mapping_matched", score_positions=score_positions)
            return None

        # Per-dimension current relationship filtering
        matching_mappings: List[Dict[str, Any]] = []
        for dimension_name, dim_candidates in dimension_matches.items():
            if current_relationship_id is not None:
                current_in_dim = any(
                    int(m["relationship"].id) == int(current_relationship_id) for m in dim_candidates
                )
                if current_in_dim:
                    # Filter to keep only current relationship in this dimension
                    dim_candidates = [
                        m for m in dim_candidates if int(m["relationship"].id) == int(current_relationship_id)
                    ]
            matching_mappings.extend(dim_candidates)

        if not matching_mappings:
            logger.debug("no_mappings_after_dimension_filtering")
            return None

        # Build unique candidate set aggregated by relationship_id with max priority
        unique: Dict[int, Dict[str, Any]] = {}
        for m in matching_mappings:
            rid = int(m["relationship"].id)
            pr = int(m.get("priority", 0))
            if rid not in unique:
                unique[rid] = {
                    "relationship": m["relationship"],
                    "dimension_name": m["dimension_name"],
                    "start_position": m["start_position"],
                    "end_position": m["end_position"],
                    "priority": pr,
                    "limit_count": m.get("limit_count"),
                }
            else:
                if pr > unique[rid]["priority"]:
                    unique[rid]["priority"] = pr

        if not unique:
            logger.debug("no_unique_candidates_after_match")
            return None

        # Enforce limit_count using relationship_counts
        if relationship_counts:
            filtered: Dict[int, Dict[str, Any]] = {}
            for rid, data in unique.items():
                limit = int(data.get("limit_count") or 0)
                if limit <= 0:
                    filtered[rid] = data
                    continue
                cnt = relationship_counts.get(str(rid))
                if cnt is None:
                    cnt = relationship_counts.get(rid, 0)
                try:
                    cnt_int = int(cnt or 0)
                except Exception:
                    cnt_int = 0
                if cnt_int > limit:
                    logger.error(
                        "relationship_count_anomaly_gt_limit",
                        relationship_id=rid,
                        count=cnt_int,
                        limit=limit,
                    )
                    continue
                if cnt_int >= limit:
                    continue
                filtered[rid] = data
            unique = filtered

        if not unique:
            logger.error("no_candidate_after_limit_filter")
            return None

        # Select by priority: higher number = higher priority
        top_priority = max(v["priority"] for v in unique.values())
        top_relations = [v for v in unique.values() if v["priority"] == top_priority]

        if len(top_relations) > 1:
            logger.error("priority_tie_detected", top_priority=top_priority, candidates=len(top_relations))
            return None

        selected_mapping = top_relations[0]

        logger.debug(
            "relationship_mapping_selected",
            relationship_id=selected_mapping["relationship"].id,
            priority=selected_mapping.get("priority", 0),
            candidates_count=len(unique),
            current_relationship_id=current_relationship_id,
        )

        return selected_mapping

    except Exception as e:
        logger.error(
            "relationship_matching_failed",
            error=str(e),
            score_positions=score_positions,
            mappings_count=len(relationship_mappings),
            current_relationship_id=current_relationship_id,
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


async def calculate_new_scores(
    db: AsyncSession, character_info: Dict[str, Any], llm_response_scores: Dict[str, int]
) -> Dict[str, int]:
    """
    Calculate new relationship scores based on LLM response.

    Args:
        db: Database session
        character_info: Character information dictionary
        llm_response_scores: Scores from LLM response

    Returns:
        Dictionary of dimension_name -> new_score

    Raises:
        AIRelationshipError: If calculation fails
    """
    try:
        character_id = character_info.get("character_id")
        if not character_id:
            raise AIRelationshipError(
                operation="calculate_new_scores",
                reason="missing_character_id",
                message="No character_id in character_info",
            )

        # Get all dimensions with offset config in one query
        from crud.ai.character_dimension import get_by_character
        current_scores = await get_by_character(db, character_id)

        if not current_scores:
            logger.warning(
                "no_current_scores_for_calculation",
                character_id=character_id,
            )
            return llm_response_scores

        # Build dimension config map
        from .utils.position_mapping import map_score_to_position
        from .conversation_prompt import get_response_schema
        from .utils.score_mapping import map_to_permille

        # Load JSON Schema to get per-dimension min/max for mapping
        character_qiao_id = None
        try:
            character_obj = character_info.get("character")
            if character_obj is not None:
                character_qiao_id = getattr(character_obj, "qiao_id", None)
        except Exception:
            character_qiao_id = None

        if not character_qiao_id:
            raise AIRelationshipError(
                operation="calculate_new_scores",
                reason="missing_character_qiao_id",
                message="No character.qiao_id in character_info",
            )

        schema = await get_response_schema(db, character_qiao_id)
        # Validate schema structure
        try:
            score_schema_props = (
                schema.get("properties", {}).get("score", {}).get("properties", {})
            )
            if not isinstance(score_schema_props, dict) or not score_schema_props:
                raise KeyError("invalid_score_schema")
        except Exception as e:
            logger.error("json_schema_invalid_for_mapping", error=str(e))
            raise AIRelationshipError(
                operation="calculate_new_scores",
                reason="schema_invalid",
                message="JSON Schema for score mapping is invalid",
            )

        new_scores = {}
        for score_data in current_scores:
            dimension_name = score_data["dimension_name"]
            current_score = score_data["score"]
            initial_position = score_data["initial_position"]

            # Get LLM response score for this dimension
            llm_score = llm_response_scores.get(dimension_name)
            if llm_score is None:
                new_scores[dimension_name] = current_score
                continue

            # Get dimension-specific offset config
            algorithm = score_data.get("position_mapping_algorithm", 1)
            params = score_data.get("position_mapping_params", {})

            # Map raw score to 0-1000 using JSON Schema min/max
            dim_schema = score_schema_props.get(dimension_name)
            if not isinstance(dim_schema, dict):
                raise AIRelationshipError(
                    operation="calculate_new_scores",
                    reason="schema_missing_dimension",
                    message=f"Missing schema for dimension {dimension_name}",
                )
            min_v = dim_schema.get("minimum")
            max_v = dim_schema.get("maximum")
            try:
                mapped = map_to_permille(float(llm_score), float(min_v), float(max_v))
            except Exception as e:
                raise AIRelationshipError(
                    operation="calculate_new_scores",
                    reason="schema_mapping_failed",
                    message=f"Mapping failed for dimension {dimension_name}: {str(e)}",
                )

            # Apply position mapping algorithm on mapped value
            new_pos = map_score_to_position(
                algorithm=algorithm,
                score=float(mapped),
                initial_position=initial_position,
                params=params or {},
            )
            # Final integer output for both score and position semantics (half-up rounding)
            try:
                # half-up: consistent with JS Math.round to avoid UI/backend mismatch
                final_int = int(float(new_pos) + 0.5)
            except Exception:
                final_int = int(new_pos)
            new_scores[dimension_name] = max(0, min(1000, final_int))

        logger.debug(
            "new_scores_calculated",
            character_id=character_id,
            current_scores_count=len(current_scores),
            new_scores_count=len(new_scores),
        )

        return new_scores

    except Exception as e:
        logger.error(
            "new_scores_calculation_failed",
            error=str(e),
            character_info=character_info,
            llm_response_scores=llm_response_scores,
        )
        raise AIRelationshipError(
            operation="calculate_new_scores",
            reason="calculation_failed",
            message=f"Failed to calculate new scores: {str(e)}",
        )


async def update_relationship_positions(
    db: AsyncSession, character_id: int, new_scores: Dict[str, int]
) -> bool:
    """
    Update relationship positions based on new scores.

    Args:
        db: Database session
        character_id: Character ID
        new_scores: Dictionary of dimension_name -> new_score

    Returns:
        True if successful, False otherwise

    Raises:
        AIRelationshipError: If update fails
    """
    try:
        # Convert dimension names to IDs for the update function
        # The update_relationship_scores function expects Dict[int, int]
        # but we have Dict[str, int], so we need to convert

        # For now, we'll use the existing update_relationship_scores function
        # which handles the position calculation internally
        success = await update_relationship_scores(db, character_id, new_scores)

        if success:
            logger.debug(
                "relationship_positions_updated",
                character_id=character_id,
                scores_count=len(new_scores),
            )
        else:
            logger.warning(
                "relationship_positions_update_failed",
                character_id=character_id,
                scores_count=len(new_scores),
            )

        return success

    except Exception as e:
        logger.error(
            "relationship_positions_update_failed",
            error=str(e),
            character_id=character_id,
            new_scores=new_scores,
        )
        raise AIRelationshipError(
            operation="update_relationship_positions",
            reason="update_failed",
            message=f"Failed to update relationship positions: {str(e)}",
        )
