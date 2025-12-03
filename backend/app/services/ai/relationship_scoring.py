"""
AI relationship scoring and type determination module.

This module handles relationship score management and relationship type determination
based on AI style configurations and score positions.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.ai.instance_dimension import get_by_instance
from app.exceptions import AIRelationshipError
from app.models.ai import AIInstance
from app.models.ai.instance_dimension import AIInstanceDimension
from app.models.ai.style import AIStyleDimension
from app.services.ai.response_schema import build_response_schema
from app.services.ai.types import InstanceContext
from app.utils.logging import get_logger

from .queries import (
    get_instance_id_by_qiao_id,
    get_instance_relationship_scores,
    get_style_with_relationships,
)
from .queries.updates import set_instance_current_relationship
from .queries.updates import (
    update_instance_relationship_scores as _update_instance_relationship_scores,
)
from .utils.position_mapping import map_score_to_position
from .utils.score_mapping import map_to_permille

logger = get_logger(__name__)


# Exception classes moved to exceptions/business.py for consistency


async def get_relationship_scores(
    db: AsyncSession, instance_qiao_id: str, auto_initialize: bool = True
) -> list[dict[str, Any]] | None:
    """
    Get relationship scores for an instance.
    Auto-initialize scores based on initial_position if missing.

    Args:
        db: Database session
        instance_qiao_id: Instance's qiao_id
        auto_initialize: Whether to auto-initialize scores if missing (default: True)

    Returns:
        List of score dictionaries, or None if not found
    """
    try:
        instance_id = await get_instance_id_by_qiao_id(db, instance_qiao_id)
        if not instance_id:
            logger.warning("instance_not_found_for_scores", instance_qiao_id=instance_qiao_id)
            return None

        scores = await get_instance_relationship_scores(db, instance_id)

        if not scores and auto_initialize:
            style_id = await _get_instance_style_id(db, instance_id)
            if not style_id:
                logger.error(
                    "instance_style_missing_for_score_init",
                    instance_qiao_id=instance_qiao_id,
                    instance_id=instance_id,
                )
            else:
                try:
                    await initialize_relationship_scores(db, instance_id, style_id)
                    scores = await get_instance_relationship_scores(db, instance_id)
                    if scores:
                        logger.info(
                            "relationship_scores_auto_initialized",
                            instance_qiao_id=instance_qiao_id,
                            style_id=style_id,
                        )
                except AIRelationshipError as init_error:
                    logger.error(
                        "relationship_score_autoinit_failed",
                        error=str(init_error),
                        instance_qiao_id=instance_qiao_id,
                        instance_id=instance_id,
                    )
                    return None

        if not scores:
            logger.info(
                "no_relationship_scores_found",
                instance_qiao_id=instance_qiao_id,
            )
            return None

        logger.debug(
            "relationship_scores_retrieved",
            instance_qiao_id=instance_qiao_id,
            score_count=len(scores),
        )

        return scores

    except Exception as e:
        logger.error(
            "relationship_scores_retrieval_failed",
            error=str(e),
            instance_qiao_id=instance_qiao_id,
        )
        # Non-fatal error: return None and log error
        return None


async def _get_instance_style_id(db: AsyncSession, instance_id: int) -> int | None:
    """
    Fetch the style_id for a given instance.
    """
    try:
        result = await db.execute(select(AIInstance.style_id).where(AIInstance.id == instance_id))
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(
            "instance_style_lookup_failed",
            error=str(e),
            instance_id=instance_id,
        )
        return None


async def initialize_relationship_scores(
    db: AsyncSession,
    instance_id: int,
    style_id: int,
    position_mapping_config: dict[str, Any] | None = None,
) -> None:
    """
    Initialize relationship scores based on dimension initial_position.

    Args:
        db: Database session
        instance_id: Instance ID
        style_id: Style ID
        position_mapping_config: Per-dimension position mapping configuration from template

    Returns:
        None (scores are created and committed to database)

    Raises:
        AIRelationshipError: If initialization fails
    """
    try:
        # Get all dimensions for this style with dimension relationship loaded
        stmt = (
            select(AIStyleDimension)
            .options(selectinload(AIStyleDimension.dimension))
            .where(AIStyleDimension.style_id == style_id)
        )
        result = await db.execute(stmt)
        style_dimensions = result.scalars().all()

        if not style_dimensions:
            raise AIRelationshipError(
                operation="initialize_relationship_scores",
                reason="dimensions_not_found",
                message=f"No dimensions found for style {style_id}",
            )

        # Get position mapping config from template
        offset_config = position_mapping_config or {}

        # Create dimension records
        for style_dimension in style_dimensions:
            # Get offset config for this dimension using the dimension name
            dim_config = offset_config.get(style_dimension.dimension.name, {})
            algorithm = dim_config.get("algorithm", 1)
            params = dim_config.get("params", {})

            dimension_record = AIInstanceDimension(
                instance_id=instance_id,
                dimension_id=style_dimension.dimension_id,
                score=style_dimension.initial_position,
                position=style_dimension.initial_position,
                position_mapping_algorithm=algorithm,
                position_mapping_params=params,
            )
            db.add(dimension_record)

        await db.commit()

        logger.info(
            "relationship_scores_initialized",
            instance_id=instance_id,
            scores_count=len(style_dimensions),
        )

    except AIRelationshipError:
        raise
    except Exception as e:
        logger.error(
            "relationship_scores_initialization_failed",
            error=str(e),
            instance_id=instance_id,
            exc_info=True,
        )
        raise AIRelationshipError(
            operation="initialize_relationship_scores",
            reason="initialization_failed",
            message=f"Failed to initialize relationship scores: {e!s}",
        )


async def determine_relationship_type(
    db: AsyncSession, context: InstanceContext, scores: list[dict[str, Any]] | None
) -> dict[str, Any] | None:
    """
    Determine relationship type based on instance style and scores.

    Args:
        db: Database session
        context: Instance context dictionary
        scores: List of relationship scores

    Returns:
        Dictionary containing relationship information, or None if not determined
    """
    try:
        style_id = context["style"]["id"]
        if not style_id:
            logger.warning(
                "no_style_id_in_context",
                instance_qiao_id=context.get("instance_qiao_id"),
            )
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
        current_relationship_id = context.get("relationship_id")
        relationship_counts = context.get("relationship_counts") or {}

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
            instance_qiao_id=context.get("instance_qiao_id"),
            scores=scores,
        )
        raise AIRelationshipError(
            operation="determine_relationship_type",
            reason="processing_failed",
            message=f"Failed to determine relationship type: {e!s}",
        )


async def update_instance_relationship_scores(
    db: AsyncSession, instance_id: int, new_scores: dict[int, int]
) -> bool:
    """
    Update relationship scores for an instance.

    Args:
        db: Database session
        instance_id: Instance ID
        new_scores: Dictionary of score_order -> score_value

    Returns:
        True if successful, False otherwise
    """
    try:
        success = await _update_instance_relationship_scores(db, instance_id, new_scores)

        if success:
            logger.debug(
                "relationship_scores_updated",
                instance_id=instance_id,
                scores=new_scores,
            )
        else:
            logger.warning(
                "relationship_scores_update_failed",
                instance_id=instance_id,
                scores=new_scores,
            )

        return success

    except Exception as e:
        logger.error(
            "instance_relationship_scores_update_failed",
            error=str(e),
            instance_id=instance_id,
            scores=new_scores,
        )
        raise AIRelationshipError(
            operation="update_instance_relationship_scores",
            reason="update_failed",
            message=f"Failed to update relationship scores: {e!s}",
        )


async def update_instance_current_relationship(
    db: AsyncSession, instance_id: int, relationship_id: int, relationship_display_name: str
) -> bool:
    """Persist the selected current relationship across all score rows for an instance."""
    try:
        success = await set_instance_current_relationship(
            db,
            instance_id=instance_id,
            relationship_id=relationship_id,
            relationship_display_name=relationship_display_name,
        )

        if success:
            logger.debug(
                "current_relationship_persisted",
                instance_id=instance_id,
                relationship_id=relationship_id,
                relationship_display_name=relationship_display_name,
            )
        else:
            logger.warning(
                "current_relationship_persist_failed",
                instance_id=instance_id,
                relationship_id=relationship_id,
            )

        return success

    except Exception as e:
        logger.error(
            "update_current_relationship_failed",
            error=str(e),
            instance_id=instance_id,
            relationship_id=relationship_id,
        )
        raise AIRelationshipError(
            operation="update_current_relationship",
            reason="update_failed",
            message=f"Failed to update current relationship: {e!s}",
        )


def _calculate_score_positions(scores: list[dict[str, Any]]) -> dict[int, int]:
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
    score_positions: dict[int, int],
    relationship_mappings: list[dict[str, Any]],
    current_relationship_id: int | None = None,
    relationship_counts: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """
    Find relationship mapping that matches the score positions.

    Implements per-dimension current relationship filtering: within each dimension,
    if current relationship is among candidates, filter out other relationships.

    Args:
        score_positions: Dictionary of dimension_name -> position
        relationship_mappings: List of relationship mapping dictionaries
        current_relationship_id: Current relationship ID for per-dimension filtering
        relationship_counts: Instance-level relationship counts for limit_count enforcement

    Returns:
        Matching relationship mapping, or None if no match
    """
    try:
        # Group matching mappings by dimension
        dimension_matches: dict[str, list[dict[str, Any]]] = {}

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
        matching_mappings: list[dict[str, Any]] = []
        for dimension_name, dim_candidates in dimension_matches.items():
            if current_relationship_id is not None:
                current_in_dim = any(
                    int(m["relationship"].id) == int(current_relationship_id)
                    for m in dim_candidates
                )
                if current_in_dim:
                    # Filter to keep only current relationship in this dimension
                    dim_candidates = [
                        m
                        for m in dim_candidates
                        if int(m["relationship"].id) == int(current_relationship_id)
                    ]
            matching_mappings.extend(dim_candidates)

        if not matching_mappings:
            logger.debug("no_mappings_after_dimension_filtering")
            return None

        # Build unique candidate set aggregated by relationship_id with max priority
        unique: dict[int, dict[str, Any]] = {}
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
            elif pr > unique[rid]["priority"]:
                unique[rid]["priority"] = pr

        if not unique:
            logger.debug("no_unique_candidates_after_match")
            return None

        # Enforce limit_count using relationship_counts
        if relationship_counts:
            filtered: dict[int, dict[str, Any]] = {}
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
            logger.error(
                "priority_tie_detected", top_priority=top_priority, candidates=len(top_relations)
            )
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
    relationship_mappings: list[dict[str, Any]],
) -> dict[str, Any] | None:
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
    db: AsyncSession, context: InstanceContext, llm_response_scores: dict[str, int]
) -> dict[str, int]:
    """
    Calculate new relationship scores based on LLM response.

    Args:
        db: Database session
        context: Instance context dictionary
        llm_response_scores: Scores from LLM response

    Returns:
        Dictionary of dimension_name -> new_score

    Raises:
        AIRelationshipError: If calculation fails
    """
    try:
        instance_id = context.get("instance_id")
        if not instance_id:
            raise AIRelationshipError(
                operation="calculate_new_scores",
                reason="missing_instance_id",
                message="Instance context missing instance_id",
            )

        # Get all dimensions with offset config in one query
        current_scores = await get_by_instance(db, instance_id)

        if not current_scores:
            logger.warning(
                "no_current_scores_for_calculation",
                instance_id=instance_id,
            )
            return llm_response_scores

        # Build dimension config map
        # Load JSON Schema to get per-dimension min/max for mapping
        schema = build_response_schema(context)
        # Validate schema structure
        try:
            score_schema_props = schema.get("properties", {}).get("score", {}).get("properties", {})
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
                    message=f"Mapping failed for dimension {dimension_name}: {e!s}",
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
            instance_id=instance_id,
            current_scores_count=len(current_scores),
            new_scores_count=len(new_scores),
        )

        return new_scores

    except Exception as e:
        logger.error(
            "new_scores_calculation_failed",
            error=str(e),
            instance_qiao_id=context.get("instance_qiao_id"),
            llm_response_scores=llm_response_scores,
        )
        raise AIRelationshipError(
            operation="calculate_new_scores",
            reason="calculation_failed",
            message=f"Failed to calculate new scores: {e!s}",
        )


async def update_relationship_positions(
    db: AsyncSession, instance_id: int, new_scores: dict[str, int]
) -> bool:
    """
    Update relationship positions based on new scores.

    Args:
        db: Database session
        instance_id: Instance ID
        new_scores: Dictionary of dimension_name -> new_score

    Returns:
        True if successful, False otherwise

    Raises:
        AIRelationshipError: If update fails
    """
    try:
        # Convert dimension names to IDs for the update function
        # The update_instance_relationship_scores function expects Dict[int, int]
        # but we have Dict[str, int], so we need to convert

        # For now, we'll use the existing update_instance_relationship_scores function
        # which handles the position calculation internally
        success = await _update_instance_relationship_scores(db, instance_id, new_scores)

        if success:
            logger.debug(
                "relationship_positions_updated",
                instance_id=instance_id,
                scores_count=len(new_scores),
            )
        else:
            logger.warning(
                "relationship_positions_update_failed",
                instance_id=instance_id,
                scores_count=len(new_scores),
            )

        return success

    except Exception as e:
        logger.error(
            "relationship_positions_update_failed",
            error=str(e),
            instance_id=instance_id,
            new_scores=new_scores,
        )
        raise AIRelationshipError(
            operation="update_relationship_positions",
            reason="update_failed",
            message=f"Failed to update relationship positions: {e!s}",
        )
