"""
AI business query layer - simple update operations.

This module provides simple update operations that typically call crud layer
or perform single-entity updates.
"""

from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from models.ai import AIContext, AICharacterDimension, AICharacter
from utils.logging import get_logger
from .character_queries import get_character_id_by_qiao_id, get_user_id_by_qiao_id

logger = get_logger(__name__)


async def save_context_entry(db: AsyncSession, context_data: Dict[str, Any]) -> Optional[int]:
    """
    Save a new context entry.

    Args:
        db: Database session
        context_data: Context data dictionary

    Returns:
        Context ID (int) if successful, None if failed
    """
    try:
        # Query character_id and user_id from qiao_ids
        character_id = await get_character_id_by_qiao_id(db, context_data["character_qiao_id"])
        user_id = await get_user_id_by_qiao_id(db, context_data["user_qiao_id"])

        if character_id is None:
            logger.error(
                "character_id_not_found_for_context",
                character_qiao_id=context_data["character_qiao_id"],
            )
            return None

        if user_id is None:
            logger.error(
                "user_id_not_found_for_context",
                user_qiao_id=context_data["user_qiao_id"],
            )
            return None

        context = AIContext(
            character_id=character_id,
            character_qiao_id=context_data["character_qiao_id"],
            user_id=user_id,
            user_qiao_id=context_data["user_qiao_id"],
            role=context_data["role"],
            content=context_data["content"],
            aggregate_state=context_data.get("aggregate_state"),
        )

        # Optional aggregation/buffer fields
        if "first_msg_id_client" in context_data:
            context.first_msg_id_client = context_data.get("first_msg_id_client")
        if "last_msg_id_client" in context_data:
            context.last_msg_id_client = context_data.get("last_msg_id_client")
        if "token_count" in context_data:
            context.token_count = context_data.get("token_count")
        if "is_attack" in context_data:
            # keep explicit assignment only when provided
            context.is_attack = 1 if context_data.get("is_attack") else 0
        if "last_msg_time_ms" in context_data:
            context.last_msg_time_ms = context_data.get("last_msg_time_ms")
        if "buffer_expires_at_ms" in context_data:
            context.buffer_expires_at_ms = context_data.get("buffer_expires_at_ms")
        if "micro_expires_at_ms" in context_data:
            context.micro_expires_at_ms = context_data.get("micro_expires_at_ms")
        if "macro_expires_at_ms" in context_data:
            context.macro_expires_at_ms = context_data.get("macro_expires_at_ms")
        if "last_message_category" in context_data:
            context.last_message_category = context_data.get("last_message_category")

        db.add(context)
        await db.flush()

        context_id = context.id

        logger.debug(
            "context_entry_saved",
            context_id=context_id,
            character_id=character_id,
            user_id=user_id,
            user_qiao_id=context_data["user_qiao_id"],
            character_qiao_id=context_data["character_qiao_id"],
        )

        return context_id

    except Exception as e:
        logger.error("context_save_failed", error=str(e), context_data=context_data)
        return None


async def update_context_status(db: AsyncSession, context_id: int, status: int) -> bool:
    """
    Update context aggregate state.

    Args:
        db: Database session
        context_id: Context ID
        status: New status (1=OPEN, 2=LOCKED, 3=COMPLETE, 4=CANCELLED)

    Returns:
        True if successful, False otherwise
    """
    try:
        result = await db.execute(select(AIContext).where(AIContext.id == context_id))
        context = result.scalar_one_or_none()

        if not context:
            logger.warning("context_not_found_for_status_update", context_id=context_id)
            return False

        old_status = context.aggregate_state
        context.aggregate_state = status
        await db.flush()

        logger.debug(
            "context_status_updated", context_id=context_id, old_status=old_status, new_status=status
        )

        return True

    except Exception as e:
        logger.error("context_status_update_failed", error=str(e), context_id=context_id, status=status)
        return False


async def is_context_locked(db: AsyncSession, context_id: int) -> bool:
    """
    Check whether the given context is still LOCKED.
    """
    try:
        result = await db.execute(select(AIContext.aggregate_state).where(AIContext.id == context_id))
        state = result.scalar_one_or_none()
        return state == 2  # AIAggregateState.LOCKED
    except Exception as e:
        logger.error("context_locked_check_failed", error=str(e), context_id=context_id)
        return False


async def finalize_context_if_locked(db: AsyncSession, context_id: int) -> bool:
    """
    Atomically set context to COMPLETE iff it's currently LOCKED.

    Returns True if updated, False otherwise. Caller is responsible for committing.
    """
    try:
        result = await db.execute(
            update(AIContext)
            .where(AIContext.id == context_id, AIContext.aggregate_state == 2)
            .values(aggregate_state=3)
        )
        updated = (result.rowcount or 0) > 0
        logger.debug("context_finalize_attempt", context_id=context_id, updated=updated)
        return updated
    except Exception as e:
        logger.error("context_finalize_failed", error=str(e), context_id=context_id)
        return False


async def update_relationship_scores(
    db: AsyncSession, character_id: int, new_scores: Dict[str, int]
) -> bool:
    """
    Update relationship scores for a character.

    Args:
        db: Database session
        character_id: Character ID
        new_scores: Dictionary of score updates {dimension_name: new_value}

    Returns:
        True if successful, False otherwise
    """
    try:
        # Get existing scores for this character with dimension names
        from models.ai import AIDimension
        result = await db.execute(
            select(AICharacterDimension, AIDimension.name)
            .join(
                AIDimension,
                AICharacterDimension.dimension_id == AIDimension.id,
            )
            .where(AICharacterDimension.character_id == character_id)
        )
        rows = result.all()
        existing_scores = {dim_name: score for (score, dim_name) in rows}

        updated_count = 0
        for dimension_name, new_value in new_scores.items():
            if dimension_name in existing_scores:
                score_obj = existing_scores[dimension_name]
                old_value = score_obj.score
                score_obj.score = new_value

                # Position calculation should be done based on score conversion algorithm
                # For now, use a simple linear mapping (this should be improved later)
                # Both score and position use 0-1000 range
                position = min(1000, max(0, int(new_value)))
                score_obj.position = position

                updated_count += 1

                logger.debug(
                    "relationship_score_updated",
                    character_id=character_id,
                    dimension_name=dimension_name,
                    old_value=old_value,
                    new_value=new_value,
                    position=score_obj.position,
                )

        if updated_count > 0:
            await db.flush()
            logger.debug(
                "relationship_scores_batch_updated",
                character_id=character_id,
                updated_count=updated_count,
            )
        else:
            logger.warning(
                "relationship_scores_no_dimension_matched",
                character_id=character_id,
                provided_dimensions=list(new_scores.keys()),
                existing_dimensions=list(existing_scores.keys()),
            )

        return updated_count > 0

    except Exception as e:
        logger.error(
            "relationship_scores_update_failed",
            error=str(e),
            character_id=character_id,
            new_scores=new_scores,
        )
        return False


async def set_current_relationship(
    db: AsyncSession, character_id: int, relationship_id: int, relationship_display_name: str
) -> bool:
    """
    Set current relationship for all score rows of a character.

    Args:
        db: Database session
        character_id: Character ID
        relationship_id: Selected relationship ID
        relationship_display_name: Display name of relationship

    Returns:
        True if updated at least one row, False otherwise
    """
    try:
        result = await db.execute(select(AICharacter).where(AICharacter.id == character_id))
        character = result.scalar_one_or_none()
        if not character:
            logger.warning("character_not_found_for_relationship_update", character_id=character_id)
            return False

        old_id = character.relationship_id
        character.relationship_id = relationship_id
        await db.flush()

        # Increment relationship_counts only when relationship actually changes
        if old_id != relationship_id:
            try:
                await increment_relationship_count(db, character_id, relationship_id)
            except Exception as inc_err:
                logger.error(
                    "increment_relationship_count_failed",
                    error=str(inc_err),
                    character_id=character_id,
                    relationship_id=relationship_id,
                )

        logger.debug(
            "current_relationship_set",
            character_id=character_id,
            relationship_id=relationship_id,
            relationship_display_name=relationship_display_name,
        )
        return True

    except Exception as e:
        logger.error(
            "set_current_relationship_failed",
            error=str(e),
            character_id=character_id,
            relationship_id=relationship_id,
        )
        return False


async def increment_relationship_count(db: AsyncSession, character_id: int, relationship_id: int) -> bool:
    """
    Increment relationship usage count in ai_characters.relationship_counts (JSONB).

    Args:
        db: Database session
        character_id: Character ID
        relationship_id: Relationship ID to increment

    Returns:
        True if updated, False otherwise
    """
    try:
        result = await db.execute(select(AICharacter).where(AICharacter.id == character_id))
        character = result.scalar_one_or_none()
        if not character:
            logger.warning("character_not_found_for_count_increment", character_id=character_id)
            return False

        counts = character.relationship_counts or {}
        key = str(int(relationship_id))
        try:
            counts[key] = int(counts.get(key, 0)) + 1
        except Exception:
            counts[key] = 1
        character.relationship_counts = counts
        await db.flush()

        logger.debug(
            "relationship_count_incremented",
            character_id=character_id,
            relationship_id=relationship_id,
            new_count=counts.get(key, 0),
        )

        return True
    except Exception as e:
        logger.error(
            "relationship_count_increment_failed",
            error=str(e),
            character_id=character_id,
            relationship_id=relationship_id,
        )
        return False


async def mark_context_as_attack(db: AsyncSession, context_id: int) -> bool:
    """
    Mark context as containing attack/injection.

    Args:
        db: Database session
        context_id: Context ID

    Returns:
        True if successful, False otherwise
    """
    try:
        result = await db.execute(select(AIContext).where(AIContext.id == context_id))
        context = result.scalar_one_or_none()

        if context:
            context.is_attack = 1
            await db.flush()

            logger.warning(
                "context_marked_as_attack",
                context_id=context_id,
                user_qiao_id=context.user_qiao_id,
                character_qiao_id=context.character_qiao_id,
            )
            return True
        else:
            logger.warning("context_not_found_for_attack_marking", context_id=context_id)
            return False

    except Exception as e:
        logger.error("context_attack_marking_failed", error=str(e), context_id=context_id)
        return False


async def update_character_memory(db: AsyncSession, character_qiao_id: str, new_memory: str) -> bool:
    """
    Update character memory.

    Args:
        db: Database session
        character_qiao_id: Character's qiao_id
        new_memory: New memory content

    Returns:
        True if successful, False otherwise
    """
    try:
        result = await db.execute(select(AICharacter).where(AICharacter.qiao_id == character_qiao_id))
        character = result.scalar_one_or_none()

        if not character:
            logger.warning("character_not_found_for_memory_update", character_qiao_id=character_qiao_id)
            return False

        old_memory = character.memory
        character.memory = new_memory
        await db.flush()

        logger.debug(
            "character_memory_updated",
            character_qiao_id=character_qiao_id,
            old_memory_length=len(old_memory) if old_memory else 0,
            new_memory_length=len(new_memory),
        )

        return True

    except Exception as e:
        logger.error(
            "character_memory_update_failed",
            error=str(e),
            character_qiao_id=character_qiao_id,
        )
        return False


async def update_character_status(db: AsyncSession, character_qiao_id: str, status: int) -> bool:
    """
    Update character status.

    Args:
        db: Database session
        character_qiao_id: Character's qiao_id
        status: New status (1=active, 2=inactive, 3=blocked)

    Returns:
        True if successful, False otherwise
    """
    try:
        result = await db.execute(select(AICharacter).where(AICharacter.qiao_id == character_qiao_id))
        character = result.scalar_one_or_none()

        if not character:
            logger.warning("character_not_found_for_status_update", character_qiao_id=character_qiao_id)
            return False

        old_status = character.status
        character.status = status
        await db.flush()

        logger.debug(
            "character_status_updated",
            character_qiao_id=character_qiao_id,
            old_status=old_status,
            new_status=status,
        )

        return True

    except Exception as e:
        logger.error(
            "character_status_update_failed",
            error=str(e),
            character_qiao_id=character_qiao_id,
            status=status,
        )
        return False
