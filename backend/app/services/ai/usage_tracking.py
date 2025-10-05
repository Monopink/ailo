"""
AI usage tracking service.

This module handles automatic usage_count updates for AI configuration entities
(personalities, styles, relationships) and enforces status modification restrictions.
"""

from typing import Literal
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.ai import AIPersonality, AIStyle, AIRelationship
from enums.common import AIStyleStatus, AIPersonalityStatus, AIRelationshipStatus
from exceptions import AIServiceError
from utils.logging import get_logger

logger = get_logger(__name__)

# Type alias for entity types
EntityType = Literal["personality", "style", "relationship"]


async def increment_usage_count(
    db: AsyncSession,
    entity_type: EntityType,
    entity_id: int,
) -> None:
    """
    Increment usage_count for an entity.

    Args:
        db: Database session
        entity_type: Type of entity (personality, style, relationship)
        entity_id: Entity ID

    Raises:
        AIServiceError: If entity not found or update fails
    """
    try:
        model_class = _get_model_class(entity_type)

        # Increment usage_count
        result = await db.execute(
            update(model_class)
            .where(model_class.id == entity_id)
            .values(usage_count=model_class.usage_count + 1)
            .returning(model_class.usage_count)
        )

        new_count = result.scalar_one_or_none()

        if new_count is None:
            raise AIServiceError(
                ai_service="usage_tracking",
                reason=f"{entity_type}_not_found",
                message=f"{entity_type.capitalize()} with ID {entity_id} not found",
            )

        logger.info(
            f"{entity_type}_usage_incremented",
            entity_type=entity_type,
            entity_id=entity_id,
            new_count=new_count,
        )

    except AIServiceError:
        raise
    except Exception as e:
        logger.error(
            f"{entity_type}_usage_increment_failed",
            entity_type=entity_type,
            entity_id=entity_id,
            error=str(e),
        )
        raise AIServiceError(
            ai_service="usage_tracking",
            reason=f"{entity_type}_usage_increment_failed",
            message=f"Failed to increment usage count: {str(e)}",
        )


async def decrement_usage_count(
    db: AsyncSession,
    entity_type: EntityType,
    entity_id: int,
) -> None:
    """
    Decrement usage_count for an entity.

    Args:
        db: Database session
        entity_type: Type of entity (personality, style, relationship)
        entity_id: Entity ID

    Raises:
        AIServiceError: If entity not found or update fails
    """
    try:
        model_class = _get_model_class(entity_type)

        # Decrement usage_count (ensure it doesn't go below 0)
        result = await db.execute(
            update(model_class)
            .where(model_class.id == entity_id)
            .where(model_class.usage_count > 0)
            .values(usage_count=model_class.usage_count - 1)
            .returning(model_class.usage_count)
        )

        new_count = result.scalar_one_or_none()

        if new_count is None:
            # Check if entity exists
            check_result = await db.execute(select(model_class).where(model_class.id == entity_id))
            if check_result.scalar_one_or_none() is None:
                raise AIServiceError(
                    ai_service="usage_tracking",
                    reason=f"{entity_type}_not_found",
                    message=f"{entity_type.capitalize()} with ID {entity_id} not found",
                )
            # Entity exists but usage_count is already 0
            logger.warning(
                f"{entity_type}_usage_already_zero",
                entity_type=entity_type,
                entity_id=entity_id,
            )
            return

        logger.info(
            f"{entity_type}_usage_decremented",
            entity_type=entity_type,
            entity_id=entity_id,
            new_count=new_count,
        )

    except AIServiceError:
        raise
    except Exception as e:
        logger.error(
            f"{entity_type}_usage_decrement_failed",
            entity_type=entity_type,
            entity_id=entity_id,
            error=str(e),
        )
        raise AIServiceError(
            ai_service="usage_tracking",
            reason=f"{entity_type}_usage_decrement_failed",
            message=f"Failed to decrement usage count: {str(e)}",
        )


async def validate_status_change(
    db: AsyncSession,
    entity_type: EntityType,
    entity_id: int,
    new_status: int,
) -> None:
    """
    Validate if status change is allowed based on usage_count.

    Args:
        db: Database session
        entity_type: Type of entity (personality, style, relationship)
        entity_id: Entity ID
        new_status: New status value

    Raises:
        AIServiceError: If status change is not allowed
    """
    try:
        model_class = _get_model_class(entity_type)
        status_enum = _get_status_enum(entity_type)

        # Only validate when changing to inactive status
        if new_status != status_enum.INACTIVE.value:
            return

        # Get entity with usage_count
        result = await db.execute(
            select(model_class.usage_count, model_class.status).where(model_class.id == entity_id)
        )

        row = result.one_or_none()

        if row is None:
            raise AIServiceError(
                ai_service="usage_tracking",
                reason=f"{entity_type}_not_found",
                message=f"{entity_type.capitalize()} with ID {entity_id} not found",
            )

        usage_count, current_status = row

        # Check if already inactive
        if current_status == status_enum.INACTIVE.value:
            logger.debug(
                f"{entity_type}_already_inactive",
                entity_type=entity_type,
                entity_id=entity_id,
            )
            return

        # Prevent deactivation if in use
        if usage_count > 0:
            raise AIServiceError(
                ai_service="usage_tracking",
                reason=f"{entity_type}_in_use_cannot_deactivate",
                message=f"Cannot deactivate {entity_type}: currently used by {usage_count} AI character(s)",
            )

        logger.debug(
            f"{entity_type}_status_change_validated",
            entity_type=entity_type,
            entity_id=entity_id,
            new_status=new_status,
        )

    except AIServiceError:
        raise
    except Exception as e:
        logger.error(
            f"{entity_type}_status_validation_failed",
            entity_type=entity_type,
            entity_id=entity_id,
            error=str(e),
        )
        raise AIServiceError(
            ai_service="usage_tracking",
            reason=f"{entity_type}_status_validation_failed",
            message=f"Failed to validate status change: {str(e)}",
        )


def _get_model_class(entity_type: EntityType):
    """Get SQLAlchemy model class for entity type."""
    if entity_type == "personality":
        return AIPersonality
    elif entity_type == "style":
        return AIStyle
    elif entity_type == "relationship":
        return AIRelationship
    else:
        raise ValueError(f"Unknown entity type: {entity_type}")


def _get_status_enum(entity_type: EntityType):
    """Get status enum for entity type."""
    if entity_type == "personality":
        return AIPersonalityStatus
    elif entity_type == "style":
        return AIStyleStatus
    elif entity_type == "relationship":
        return AIRelationshipStatus
    else:
        raise ValueError(f"Unknown entity type: {entity_type}")
