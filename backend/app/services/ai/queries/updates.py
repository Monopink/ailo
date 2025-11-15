"""
AI business query layer - simple update operations.

This module provides simple update operations that typically call crud layer
or perform single-entity updates.
"""

from typing import Any, Dict, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.ai import AIConversationItem, AICharacterDimension, AICharacter
from utils.logging import get_logger

logger = get_logger(__name__)


async def create_conversation_item(db: AsyncSession, item_data: Dict[str, Any]) -> Optional[int]:
    """
    Persist a new conversation item row using simple content fields.
    """
    try:
        required_fields = {"user_qiao_id", "character_qiao_id", "role", "message_type"}
        missing = required_fields - set(item_data.keys())
        if missing:
            logger.error("conversation_item_missing_fields", missing=list(missing))
            return None

        message_type = item_data["message_type"]
        text_content = item_data.get("text_content")
        media_url = item_data.get("media_url")
        media_metadata = item_data.get("media_metadata")

        if message_type == "text":
            if not text_content:
                logger.error("conversation_item_missing_text_content")
                return None
            media_url = None
            media_metadata = None
        elif message_type in {"image", "audio"}:
            if not media_url:
                logger.error("conversation_item_missing_media_url", message_type=message_type)
                return None
        else:
            logger.error("conversation_item_unknown_type", message_type=message_type)
            return None

        client_msg_ids = item_data.get("client_msg_ids") or []

        created_at_override = item_data.get("created_at")

        item = AIConversationItem(
            user_qiao_id=item_data["user_qiao_id"],
            character_qiao_id=item_data["character_qiao_id"],
            role=item_data["role"],
            message_type=message_type,
            text_content=text_content,
            media_url=media_url,
            media_metadata=media_metadata,
            buffer_id=item_data.get("buffer_id"),
            is_excluded_from_context=item_data.get("is_excluded_from_context", False),
            client_msg_ids=client_msg_ids,
        )

        if created_at_override:
            item.created_at = created_at_override

        db.add(item)
        await db.flush()

        logger.debug(
            "conversation_item_saved",
            item_id=item.id,
            user_qiao_id=item.user_qiao_id,
            character_qiao_id=item.character_qiao_id,
            role=item.role,
            message_type=message_type,
        )

        return item.id

    except Exception as exc:
        logger.error("conversation_item_save_failed", error=str(exc), item_data=item_data)
        return None


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


async def mark_conversation_item_as_excluded(
    db: AsyncSession, conversation_item_id: int
) -> bool:
    """
    Flag a conversation item so it is omitted from future LLM prompts.
    """
    try:
        result = await db.execute(
            select(AIConversationItem).where(AIConversationItem.id == conversation_item_id)
        )
        item = result.scalar_one_or_none()

        if not item:
            logger.warning("conversation_item_not_found_for_flagging", item_id=conversation_item_id)
            return False

        item.is_excluded_from_context = True
        await db.flush()

        logger.info(
            "conversation_item_marked_excluded",
            item_id=conversation_item_id,
            user_qiao_id=item.user_qiao_id,
            character_qiao_id=item.character_qiao_id,
        )
        return True

    except Exception as exc:
        logger.error(
            "conversation_item_exclude_failed",
            error=str(exc),
            item_id=conversation_item_id,
        )
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
