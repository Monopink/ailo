"""
AI data access layer - mutation functions.

This module provides all write/update functions for AI services with clear
separation of concerns and pure function design.
"""

from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.ai import AIContext, AIRelationshipScore, AIRequestLog, AICharacter
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
            source_type=context_data.get("source_type", 1),  # original
            context_metadata=context_data.get("context_metadata", {}),
            reply_status=context_data.get("reply_status", 1),  # pending
        )

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
    Update context reply status.

    Args:
        db: Database session
        context_id: Context ID
        status: New status (1=pending, 2=processing, 3=done)

    Returns:
        True if successful, False otherwise
    """
    try:
        result = await db.execute(select(AIContext).where(AIContext.id == context_id))
        context = result.scalar_one_or_none()

        if not context:
            logger.warning("context_not_found_for_status_update", context_id=context_id)
            return False

        old_status = context.reply_status
        context.reply_status = status
        await db.flush()

        logger.debug(
            "context_status_updated", context_id=context_id, old_status=old_status, new_status=status
        )

        return True

    except Exception as e:
        logger.error("context_status_update_failed", error=str(e), context_id=context_id, status=status)
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
        # Get existing scores for this character
        result = await db.execute(
            select(AIRelationshipScore).where(AIRelationshipScore.character_id == character_id)
        )
        existing_scores = {score.dimension_name: score for score in result.scalars().all()}

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

        return updated_count > 0

    except Exception as e:
        logger.error(
            "relationship_scores_update_failed",
            error=str(e),
            character_id=character_id,
            new_scores=new_scores,
        )
        return False


async def save_ai_response(db: AsyncSession, response_data: Dict[str, Any]) -> bool:
    """
    Save AI response and update related data.

    Args:
        db: Database session
        response_data: Response data dictionary

    Returns:
        True if successful, False otherwise
    """
    try:
        # Update context status to done - context_id is int internally
        if response_data.get("context_id"):
            await update_context_status(db, response_data["context_id"], 3)  # done

        # Save AI request log
        request_log = AIRequestLog(
            character_id=response_data.get("character_id"),
            user_qiao_id=response_data.get("user_qiao_id"),
            style_id=response_data.get("style_id"),
            personality_id=response_data.get("personality_id"),
            request=response_data.get("request", {}),
            response=response_data.get("response", {}),
            status=1 if response_data.get("success", False) else 2,
            token_count=response_data.get("token_count", 0),
            response_time=response_data.get("response_time", 0),
        )

        db.add(request_log)
        await db.flush()

        logger.debug(
            "ai_response_saved",
            character_id=response_data.get("character_id"),
            user_qiao_id=response_data.get("user_qiao_id"),
            success=response_data.get("success", False),
        )

        return True

    except Exception as e:
        logger.error("ai_response_save_failed", error=str(e), response_data=response_data)
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
