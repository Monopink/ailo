"""AI Instance Dimension CRUD operations.

This module provides CRUD operations for AI instance dimension scores.
"""

from dataclasses import dataclass
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai.instance import AIInstance
from app.models.ai.instance_dimension import AIInstanceDimension
from app.models.ai.style import AIDimension, AIStyleDimension
from app.services.ai.utils.position_mapping import map_score_to_position
from app.type_defs import InstanceDimensionData, JSONDict, JSONValue
from app.utils.logging import get_logger

logger = get_logger(__name__)


async def get_by_instance(db: AsyncSession, instance_id: int) -> list[InstanceDimensionData]:
    """Get all dimensions for an instance with style dimension info."""
    try:
        stmt = (
            select(
                AIInstanceDimension.dimension_id,
                AIDimension.name.label("dimension_name"),
                AIInstanceDimension.score,
                AIInstanceDimension.position,
                AIInstanceDimension.position_mapping_algorithm,
                AIInstanceDimension.position_mapping_params,
                AIStyleDimension.initial_position,
            )
            .join(AIDimension, AIInstanceDimension.dimension_id == AIDimension.id)
            .join(AIInstance, AIInstance.id == AIInstanceDimension.instance_id)
            .join(
                AIStyleDimension,
                (AIStyleDimension.style_id == AIInstance.style_id)
                & (AIStyleDimension.dimension_id == AIInstanceDimension.dimension_id),
            )
            .where(AIInstanceDimension.instance_id == instance_id)
        )
        result = await db.execute(stmt)
        # Cast to InstanceDimensionData for type safety
        return cast(list[InstanceDimensionData], [dict(row._mapping) for row in result])
    except Exception as e:
        logger.error("get_by_instance_failed", instance_id=instance_id, error=str(e))
        return []


async def update_dimension(
    db: AsyncSession,
    instance_id: int,
    dimension_id: int,
    update_data: JSONDict,
    *,
    commit: bool = True,
) -> bool:
    """Update a single dimension."""
    try:
        stmt = select(AIInstanceDimension).where(
            AIInstanceDimension.instance_id == instance_id,
            AIInstanceDimension.dimension_id == dimension_id,
        )
        result = await db.execute(stmt)
        dimension = result.scalar_one_or_none()

        if not dimension:
            logger.warning(
                "dimension_not_found",
                instance_id=instance_id,
                dimension_id=dimension_id,
            )
            return False
        for key, value in update_data.items():
            setattr(dimension, key, value)

        if commit:
            await db.commit()
        else:
            await db.flush()
    except Exception as e:
        logger.error(
            "update_dimension_failed",
            instance_id=instance_id,
            dimension_id=dimension_id,
            error=str(e),
        )
        await db.rollback()
        return False
    else:
        logger.debug("dimension_updated", instance_id=instance_id, dimension_id=dimension_id)
        return True


@dataclass(slots=True)
class DimensionPayload:
    """Validated payload for a single dimension update."""

    dimension_id: int
    score_int: int
    score_float: float
    algorithm: int
    params: JSONDict | None


async def update_dimensions_batch(
    db: AsyncSession,
    instance_id: int,
    dimensions_data: list[JSONDict],
    *,
    commit: bool = True,
) -> dict[str, int]:
    """Batch update/create instance dimensions.

    Args:
        db: Database session
        instance_id: Instance ID
        dimensions_data: List of dimension data dicts with keys:
            - dimension_id: int
            - score: int
            - position_mapping_algorithm: int
            - position_mapping_params: dict (optional)
        commit: Whether to commit transaction immediately.

    Returns:
        {"updated": int, "created": int}

    """
    try:
        # Resolve instance style_id
        style_res = await db.execute(
            select(AIInstance.style_id).where(AIInstance.id == instance_id)
        )
        style_id = style_res.scalar_one_or_none()
        if style_id is None:
            logger.error("instance_style_not_found", instance_id=instance_id)
            return {"updated": 0, "created": 0}

        # Get existing dimensions with initial_position via style join
        existing_stmt = (
            select(AIInstanceDimension, AIStyleDimension.initial_position)
            .join(
                AIStyleDimension,
                (AIStyleDimension.style_id == style_id)
                & (AIStyleDimension.dimension_id == AIInstanceDimension.dimension_id),
            )
            .where(AIInstanceDimension.instance_id == instance_id)
        )
        result = await db.execute(existing_stmt)
        existing_dimensions = {dim.dimension_id: (dim, initial_pos) for dim, initial_pos in result}

        payloads: list[DimensionPayload] = []
        for raw_dimension in dimensions_data:
            parsed = _parse_dimension_payload(raw_dimension)
            if parsed:
                payloads.append(parsed)

        if not payloads:
            logger.warning("no_valid_dimensions_to_update", instance_id=instance_id)
            return {"updated": 0, "created": 0}

        # Get initial positions for new dimensions under this style
        dimension_ids = [payload.dimension_id for payload in payloads]
        if dimension_ids:
            style_stmt = select(AIStyleDimension).where(
                (AIStyleDimension.style_id == style_id)
                & (AIStyleDimension.dimension_id.in_(dimension_ids))
            )
            result = await db.execute(style_stmt)
            style_dimensions = {
                dim.dimension_id: dim.initial_position for dim in result.scalars().all()
            }
        else:
            style_dimensions = {}

        updated = 0
        created = 0

        for payload in payloads:
            dimension_id = payload.dimension_id
            # Get initial position
            if dimension_id in existing_dimensions:
                _, initial_position = existing_dimensions[dimension_id]
            else:
                initial_position = style_dimensions.get(dimension_id)
            if initial_position is None:
                logger.error(
                    "initial_position_not_found",
                    instance_id=instance_id,
                    dimension_id=dimension_id,
                )
                # Skip this dimension (no default values)
                continue

            # Calculate position using position mapping algorithm
            try:
                position = int(
                    map_score_to_position(
                        algorithm=payload.algorithm,
                        score=payload.score_float,
                        initial_position=float(initial_position),
                        params=payload.params,
                    )
                )
            except Exception as e:
                logger.warning(
                    "position_calculation_failed_using_score",
                    dimension_id=dimension_id,
                    score=payload.score_float,
                    error=str(e),
                )
                # Fallback: use score as position
                position = payload.score_int

            if dimension_id in existing_dimensions:
                # Update existing dimension
                dimension, _ = existing_dimensions[dimension_id]
                dimension.score = payload.score_int
                dimension.position = position
                dimension.position_mapping_algorithm = payload.algorithm
                dimension.position_mapping_params = payload.params or {}
                updated += 1
            else:
                # Create new dimension
                new_dimension = AIInstanceDimension(
                    instance_id=instance_id,
                    dimension_id=dimension_id,
                    score=payload.score_int,
                    position=position,
                    position_mapping_algorithm=payload.algorithm,
                    position_mapping_params=payload.params or {},
                )
                db.add(new_dimension)
                created += 1

    except Exception as e:
        logger.error(
            "update_dimensions_batch_failed",
            instance_id=instance_id,
            error=str(e),
            exc_info=True,
        )
        await db.rollback()
        raise
    else:
        if commit:
            await db.commit()
        else:
            await db.flush()
        logger.info(
            "dimensions_batch_updated",
            instance_id=instance_id,
            updated=updated,
            created=created,
        )
        return {"updated": updated, "created": created}


def _coerce_dimension_id(value: JSONValue | None) -> int | None:
    """Convert dynamic payload values into integer dimension identifiers."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _coerce_score_value(value: JSONValue | None) -> float | None:
    """Normalize score payloads to floats."""
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _coerce_algorithm(value: JSONValue | None) -> int | None:
    """Normalize mapping algorithm identifiers."""
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _coerce_params(value: JSONValue | None) -> JSONDict | None:
    """Ensure position mapping parameters are dictionary-based."""
    if isinstance(value, dict):
        return dict(value)
    return None


def _parse_dimension_payload(raw_dimension: JSONDict) -> DimensionPayload | None:
    """Validate incoming dimension data and convert to structured payload."""
    dimension_id = _coerce_dimension_id(raw_dimension.get("dimension_id"))
    if dimension_id is None:
        logger.warning("invalid_dimension_id", data=raw_dimension)
        return None

    score_value = _coerce_score_value(raw_dimension.get("score"))
    if score_value is None:
        logger.warning("invalid_dimension_score", dimension_id=dimension_id, data=raw_dimension)
        return None

    algorithm = _coerce_algorithm(raw_dimension.get("position_mapping_algorithm"))
    if algorithm is None:
        logger.warning(
            "invalid_mapping_algorithm",
            dimension_id=dimension_id,
            algorithm=raw_dimension.get("position_mapping_algorithm"),
        )
        return None

    params = _coerce_params(raw_dimension.get("position_mapping_params"))
    score_int = int(score_value)

    return DimensionPayload(
        dimension_id=dimension_id,
        score_int=score_int,
        score_float=score_value,
        algorithm=algorithm,
        params=params,
    )
