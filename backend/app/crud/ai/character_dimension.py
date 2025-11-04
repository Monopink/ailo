"""
AI Character Dimension CRUD operations.

This module provides CRUD operations for AI character dimension scores.
"""

from typing import List, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.ai.character_dimension import AICharacterDimension
from models.ai.style import AIStyleDimension, AIDimension
from models.ai.character import AICharacter
from utils.logging import get_logger

logger = get_logger(__name__)


async def get_by_character(db: AsyncSession, character_id: int) -> List[Dict[str, Any]]:
    """Get all dimensions for a character with style dimension info."""
    try:
        stmt = (
            select(
                AICharacterDimension.dimension_id,
                AIDimension.name.label("dimension_name"),
                AICharacterDimension.score,
                AICharacterDimension.position,
                AICharacterDimension.position_mapping_algorithm,
                AICharacterDimension.position_mapping_params,
                AIStyleDimension.initial_position,
            )
            .join(AIDimension, AICharacterDimension.dimension_id == AIDimension.id)
            .join(AICharacter, AICharacter.id == AICharacterDimension.character_id)
            .join(
                AIStyleDimension,
                (AIStyleDimension.style_id == AICharacter.style_id)
                & (AIStyleDimension.dimension_id == AICharacterDimension.dimension_id),
            )
            .where(AICharacterDimension.character_id == character_id)
        )
        result = await db.execute(stmt)
        return [dict(row._mapping) for row in result]
    except Exception as e:
        logger.error("get_by_character_failed", character_id=character_id, error=str(e))
        return []


async def update_dimension(
    db: AsyncSession, character_id: int, dimension_id: int, update_data: Dict[str, Any]
) -> bool:
    """Update a single dimension."""
    try:
        stmt = select(AICharacterDimension).where(
            AICharacterDimension.character_id == character_id,
            AICharacterDimension.dimension_id == dimension_id,
        )
        result = await db.execute(stmt)
        dimension = result.scalar_one_or_none()

        if not dimension:
            logger.warning("dimension_not_found", character_id=character_id, dimension_id=dimension_id)
            return False

        for key, value in update_data.items():
            setattr(dimension, key, value)

        await db.commit()
        logger.debug("dimension_updated", character_id=character_id, dimension_id=dimension_id)
        return True
    except Exception as e:
        logger.error(
            "update_dimension_failed", character_id=character_id, dimension_id=dimension_id, error=str(e)
        )
        await db.rollback()
        return False


async def update_dimensions_batch(
    db: AsyncSession, character_id: int, dimensions_data: List[Dict[str, Any]]
) -> Dict[str, int]:
    """
    Batch update/create character dimensions.

    Args:
        db: Database session
        character_id: Character ID
        dimensions_data: List of dimension data dicts with keys:
            - dimension_id: int
            - score: int
            - position_mapping_algorithm: int
            - position_mapping_params: dict (optional)

    Returns:
        {"updated": int, "created": int}
    """
    try:
        from services.ai.utils.position_mapping import map_score_to_position

        # Resolve character style_id
        style_res = await db.execute(select(AICharacter.style_id).where(AICharacter.id == character_id))
        style_id = style_res.scalar_one_or_none()
        if style_id is None:
            logger.error("character_style_not_found", character_id=character_id)
            return {"updated": 0, "created": 0}

        # Get existing dimensions with initial_position via style join
        stmt = (
            select(AICharacterDimension, AIStyleDimension.initial_position)
            .join(
                AIStyleDimension,
                (AIStyleDimension.style_id == style_id)
                & (AIStyleDimension.dimension_id == AICharacterDimension.dimension_id),
            )
            .where(AICharacterDimension.character_id == character_id)
        )
        result = await db.execute(stmt)
        existing_dimensions = {dim.dimension_id: (dim, initial_pos) for dim, initial_pos in result}

        # Get initial positions for new dimensions under this style
        dimension_ids = [d["dimension_id"] for d in dimensions_data]
        if dimension_ids:
            stmt = select(AIStyleDimension).where(
                (AIStyleDimension.style_id == style_id) & (AIStyleDimension.dimension_id.in_(dimension_ids))
            )
            result = await db.execute(stmt)
            style_dimensions = {dim.dimension_id: dim.initial_position for dim in result.scalars().all()}
        else:
            style_dimensions = {}

        updated = 0
        created = 0

        for dim_data in dimensions_data:
            dimension_id = dim_data["dimension_id"]
            score = dim_data["score"]
            algorithm = dim_data["position_mapping_algorithm"]
            params = dim_data.get("position_mapping_params", {})

            # Get initial position
            if dimension_id in existing_dimensions:
                _, initial_position = existing_dimensions[dimension_id]
            else:
                initial_position = style_dimensions.get(dimension_id)
                if initial_position is None:
                    logger.error(
                        "initial_position_not_found",
                        character_id=character_id,
                        dimension_id=dimension_id,
                    )
                    # Skip this dimension (no default values)
                    continue

            # Calculate position using position mapping algorithm
            try:
                position = int(
                    map_score_to_position(
                        algorithm=algorithm,
                        score=float(score),
                        initial_position=float(initial_position),
                        params=params,
                    )
                )
            except Exception as e:
                logger.warning(
                    "position_calculation_failed_using_score",
                    dimension_id=dimension_id,
                    score=score,
                    error=str(e),
                )
                # Fallback: use score as position
                position = score

            if dimension_id in existing_dimensions:
                # Update existing dimension
                dimension, _ = existing_dimensions[dimension_id]
                dimension.score = score
                dimension.position = position
                dimension.position_mapping_algorithm = algorithm
                dimension.position_mapping_params = params
                updated += 1
            else:
                # Create new dimension
                new_dimension = AICharacterDimension(
                    character_id=character_id,
                    dimension_id=dimension_id,
                    score=score,
                    position=position,
                    position_mapping_algorithm=algorithm,
                    position_mapping_params=params,
                )
                db.add(new_dimension)
                created += 1

        await db.commit()

        logger.info(
            "dimensions_batch_updated",
            character_id=character_id,
            updated=updated,
            created=created,
        )

        return {"updated": updated, "created": created}

    except Exception as e:
        logger.error(
            "update_dimensions_batch_failed", character_id=character_id, error=str(e), exc_info=True
        )
        await db.rollback()
        raise
