"""
Database transaction operations for AI services.

This module provides complex transaction operations that involve multiple
database operations and require atomicity.
"""

import asyncio
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy import func, select

from models.ai import AICharacter, AIConversationItemArchive, AIRequestLog
from models.profile import Profile
from models.contact import Contact
from .updates import (
    update_relationship_scores,
    set_current_relationship,
    update_character_status,
    mark_conversation_item_as_excluded,
)
from .character_queries import get_user_id_by_qiao_id, get_character_relationship_config
from .template_queries import get_profile_template_by_id, get_character_template_by_id
from services.message.processing.sender import send_ai_messages_with_typing
from utils.logging import get_logger
logger = get_logger(__name__)

DEFAULT_TYPING_SPEED_WPM = 35
DEFAULT_TYPING_SPEED_SECONDS_PER_WORD = 60.0 / DEFAULT_TYPING_SPEED_WPM


async def create_character_with_relations(db: AsyncSession, character_data: Dict[str, Any]) -> str:
    """
    Create character with all related entities in a transaction.

    Args:
        db: Database session
        character_data: Character creation data

    Returns:
        Character qiao_id

    Raises:
        RuntimeError: If creation fails
    """
    try:
        if "typing_speed_wpm" not in character_data:
            raise ValueError("typing_speed_wpm is required to create character")

        # Create character
        character = AICharacter(
            qiao_id=character_data["qiao_id"],
            category=character_data.get("category"),
            user_qiao_id=character_data.get("user_qiao_id"),
            status=character_data.get("status", 1),
            style_id=character_data["style_id"],
            personality_id=character_data["personality_id"],
            memory=character_data.get("memory"),
            prompt_variables=character_data.get("prompt_variables", {}),
            created_by=character_data.get("created_by", 2),  # admin
            typing_speed_wpm=character_data["typing_speed_wpm"],
        )

        db.add(character)
        await db.flush()

        # Create profile
        profile = Profile(
            owner_qiao_id=character_data["qiao_id"],
            owner_type=2,  # AI type
            nickname=character_data.get("nickname"),
            gender=character_data.get("gender"),
            avatar_url=character_data.get("avatar_url"),
            bio=character_data.get("bio"),
            region=character_data.get("region"),
        )

        db.add(profile)

        # Create contact entry if user_qiao_id provided
        if character_data.get("user_qiao_id"):
            import secrets
            import string

            # Generate conv_id with random characters
            random_chars = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))
            conv_id = f"conv_{random_chars}"

            contact = Contact(
                conv_id=conv_id,
                user_qiao_id=character_data["user_qiao_id"],
                contact_type=2,  # AI type
                contact_qiao_id=character_data["qiao_id"],
                is_pinned=0,
                is_muted=0,
                is_blocked=0,
                is_deleted=0,
            )

            db.add(contact)

        await db.flush()

        logger.info(
            "character_created_with_relations",
            character_qiao_id=character_data["qiao_id"],
            user_qiao_id=character_data.get("user_qiao_id"),
        )

        return character_data["qiao_id"]

    except Exception as e:
        logger.error("character_creation_failed", error=str(e), character_data=character_data)
        raise RuntimeError(f"Failed to create character with relations: {str(e)}")


async def process_llm_response(
    db: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    user_qiao_id: str,
    character_qiao_id: str,
    character_info: Dict[str, Any],
    ai_response: Dict[str, Any],
    llm_result: Dict[str, Any],
    locked_buffer_id: Optional[int],
    user_message_item_id: Optional[int],
) -> Dict[str, Any]:
    """
    Persist LLM side effects (scores, memory, logs) and launch message sending task.
    """

    try:
        new_scores = ai_response.get("score")
        memory_operations = ai_response.get("memory_operations")

        if new_scores:
            await update_relationship_scores(db, character_info["character_id"], new_scores)

            from .relationship_queries import get_character_relationship_scores
            from ..relationship_scoring import determine_relationship_type

            latest_scores = await get_character_relationship_scores(db, character_info["character_id"])
            if latest_scores:
                rel = await determine_relationship_type(db, character_info, latest_scores)
                if rel and rel.get("relationship"):
                    relationship = rel["relationship"]
                    display_name = getattr(relationship, "display_name", getattr(relationship, "name", ""))
                    await set_current_relationship(
                        db, character_info["character_id"], relationship.id, display_name
                    )

        if memory_operations:
            from ..conversation_memory import process_memory_operations

            await process_memory_operations(db, character_qiao_id, memory_operations)

        if ai_response.get("attack_detected") and user_message_item_id:
            await mark_conversation_item_as_excluded(db, user_message_item_id)

        if ai_response.get("should_block"):
            await update_character_status(db, character_qiao_id, status=3)

        await _save_ai_request_log(
            db=db,
            character_info=character_info,
            user_qiao_id=user_qiao_id,
            ai_response=ai_response,
            llm_result=llm_result,
            buffer_id=locked_buffer_id,
        )

        if locked_buffer_id:
            from services.message.processing.buffer import finalize_buffer_if_locked

            await finalize_buffer_if_locked(db, locked_buffer_id)

        await db.commit()

        logger.info(
            "conversation_result_saved",
            user_qiao_id=user_qiao_id,
            character_qiao_id=character_qiao_id,
            buffer_id=locked_buffer_id,
        )

    except Exception as e:
        await db.rollback()
        logger.error(
            "conversation_result_save_failed",
            error=str(e),
            user_qiao_id=user_qiao_id,
            character_qiao_id=character_qiao_id,
            exc_info=True,
        )
        raise

    # Launch asynchronous sending task (typing simulation lives outside transaction)
    outgoing_messages = ai_response.get("outgoing_messages", [])
    followup_messages = ai_response.get("followup_messages", [])

    should_reply = ai_response.get("should_reply", True)
    typing_speed_seconds_per_word = DEFAULT_TYPING_SPEED_SECONDS_PER_WORD
    followup_delay_seconds = 0.0

    if should_reply and (outgoing_messages or followup_messages):
        typing_speed_seconds_per_word = await _get_typing_speed_seconds_per_word(
            db, character_qiao_id
        )
        followup_delay_ms = await _get_followup_delay_ms(db, character_qiao_id)
        if followup_delay_ms is None:
            raise ValueError("Missing followup_delay_ms configuration")
        followup_delay_seconds = followup_delay_ms / 1000.0
    else:
        outgoing_messages = []
        followup_messages = []

    asyncio.create_task(
        send_ai_messages_with_typing(
            session_factory=session_factory,
            user_qiao_id=user_qiao_id,
            character_qiao_id=character_qiao_id,
            buffer_id=locked_buffer_id,
            outgoing_messages=outgoing_messages,
            followup_messages=followup_messages,
            typing_speed_seconds_per_word=typing_speed_seconds_per_word,
            followup_delay_seconds=followup_delay_seconds,
        )
    )

    return {
        "success": True,
        "buffer_id": locked_buffer_id,
    }


async def _save_ai_request_log(
    db: AsyncSession,
    character_info: Dict[str, Any],
    user_qiao_id: str,
    ai_response: Dict[str, Any],
    llm_result: Dict[str, Any],
    buffer_id: Optional[int],
) -> None:
    """
    Save AI request log with correct field mapping.

    This fixes the field name bug: user_qiao_id (str) -> user_id (int)

    Args:
        db: Database session
        character_info: Character information dictionary
        user_qiao_id: User's qiao_id
        ai_response: AI response dictionary
        llm_result: LLM result with usage info
    """
    try:
        # Get user_id from user_qiao_id (FIX: was using user_qiao_id directly)
        user_id = await get_user_id_by_qiao_id(db, user_qiao_id)
        if not user_id:
            logger.warning("user_not_found_for_log", user_qiao_id=user_qiao_id)
            return

        request_log = AIRequestLog(
            character_id=character_info["character_id"],
            user_id=user_id,  # ✅ FIXED: use user_id (int) not user_qiao_id (str)
            style_id=character_info["style_id"],
            personality_id=character_info["personality_id"],
            request_type="production",
            provider_name=llm_result.get("config_used", {}).get("provider_name"),
            model_name=llm_result.get("model"),
            llm_config_id=(llm_result.get("config_used") or {}).get("id"),
            response_id=llm_result.get("response_id"),
            cache_hit=bool(llm_result.get("cache_hit")),
            buffer_id=buffer_id,
            request=llm_result.get("request_payload", {}),
            response=ai_response,
            status=1 if llm_result.get("success") else 2,
            token_count=llm_result.get("usage", {}).get("total_tokens", 0),
            response_time=int(llm_result.get("response_time", 0) * 1000),  # Convert to ms
        )

        db.add(request_log)
        await db.flush()

        logger.debug(
            "ai_request_log_saved",
            character_id=character_info["character_id"],
            user_id=user_id,
        )

    except Exception as e:
        logger.error("ai_request_log_save_failed", error=str(e), user_qiao_id=user_qiao_id, exc_info=True)
        # Don't raise - logging failure shouldn't break the conversation
        pass


async def _get_typing_speed_seconds_per_word(
    db: AsyncSession, character_qiao_id: str
) -> float:
    """Fetch the per-word typing latency derived from character-level WPM configuration."""

    stmt = select(AICharacter.typing_speed_wpm).where(AICharacter.qiao_id == character_qiao_id)
    result = await db.execute(stmt)
    value = result.scalar_one_or_none()

    wpm = DEFAULT_TYPING_SPEED_WPM if value is None else int(value)
    if wpm <= 0:
        logger.warning(
            "invalid_typing_speed_wpm",
            character_qiao_id=character_qiao_id,
            configured_value=wpm,
        )
        wpm = DEFAULT_TYPING_SPEED_WPM

    return 60.0 / float(wpm)


async def _get_followup_delay_ms(db: AsyncSession, character_qiao_id: str) -> Optional[int]:
    """
    Fetch relationship-specific followup delay.
    """
    config = await get_character_relationship_config(db, character_qiao_id)
    if not config:
        return None
    delay = config.get("followup_delay_ms")
    return int(delay) if delay is not None else None


async def cleanup_single_use_templates(
    db: AsyncSession, profile_template_id: int, character_template_id: int
) -> None:
    """
    Clean up single-use templates after character creation.

    Args:
        db: Database session
        profile_template_id: Profile template ID
        character_template_id: Character template ID
    """
    try:
        # Check and delete profile template if not reusable
        profile_template = await get_profile_template_by_id(db, profile_template_id)

        if profile_template and not profile_template.is_reusable:
            await db.delete(profile_template)
            logger.debug("single_use_profile_template_deleted", template_id=profile_template_id)

        # Check and delete character template if not reusable
        character_template = await get_character_template_by_id(db, character_template_id)

        if character_template and not character_template.is_reusable:
            await db.delete(character_template)
            logger.debug("single_use_character_template_deleted", template_id=character_template_id)

        await db.flush()

    except Exception as e:
        logger.error(
            "template_cleanup_failed",
            error=str(e),
            profile_template_id=profile_template_id,
            character_template_id=character_template_id,
        )
        # Non-fatal error: log but don't raise


async def archive_contexts_transaction(
    db: AsyncSession, contexts_to_archive: list, character_qiao_id: str
) -> int:
    """
    Archive contexts in a transaction.

    Args:
        db: Database session
        contexts_to_archive: List of context objects to archive
        character_qiao_id: Character's qiao_id

    Returns:
        Number of contexts archived
    """
    try:
        archived_count = 0

        for context in contexts_to_archive:
            try:
                # Create archive entry
                archive_entry = AIConversationItemArchive(
                    character_qiao_id=context.character_qiao_id,
                    user_qiao_id=context.user_qiao_id,
                    role=context.role,
                    message_type=context.message_type,
                    text_content=context.text_content,
                    media_url=context.media_url,
                    media_metadata=context.media_metadata,
                    buffer_id=context.buffer_id,
                    is_excluded_from_context=context.is_excluded_from_context,
                    created_at=context.created_at,
                    archived_at=func.now(),
                )

                db.add(archive_entry)

                # Delete from main table
                await db.delete(context)
                archived_count += 1

            except Exception as e:
                logger.error(
                    "single_context_archive_failed",
                    error=str(e),
                    conversation_item_id=context.id,
                    character_qiao_id=character_qiao_id,
                )
                continue

        await db.flush()

        logger.info(
            "contexts_archived_in_transaction",
            character_qiao_id=character_qiao_id,
            archived_count=archived_count,
            total_requested=len(contexts_to_archive),
        )

        return archived_count

    except Exception as e:
        logger.error(
            "context_archiving_transaction_failed",
            error=str(e),
            character_qiao_id=character_qiao_id,
            contexts_count=len(contexts_to_archive),
        )
        return 0


async def archive_all_conversation_items(
    db: AsyncSession, user_qiao_id: str, character_qiao_id: str
) -> int:
    """
    Archive all conversation items for a user-character pair.

    Args:
        db: Database session
        user_qiao_id: User's qiao_id
        character_qiao_id: Character's qiao_id

    Returns:
        Number of items archived
    """
    from models.ai import AIConversationItem
    from sqlalchemy import and_

    try:
        result = await db.execute(
            select(AIConversationItem).where(
                and_(
                    AIConversationItem.user_qiao_id == user_qiao_id,
                    AIConversationItem.character_qiao_id == character_qiao_id,
                )
            )
        )
        items = list(result.scalars().all())

        if not items:
            logger.info(
                "no_conversation_items_to_archive",
                user_qiao_id=user_qiao_id,
                character_qiao_id=character_qiao_id,
            )
            return 0

        archived_count = await archive_contexts_transaction(db, items, character_qiao_id)
        await db.commit()

        logger.info(
            "all_conversation_items_archived",
            user_qiao_id=user_qiao_id,
            character_qiao_id=character_qiao_id,
            archived_count=archived_count,
        )

        return archived_count

    except Exception as e:
        await db.rollback()
        logger.error(
            "archive_all_conversation_items_failed",
            error=str(e),
            user_qiao_id=user_qiao_id,
            character_qiao_id=character_qiao_id,
            exc_info=True,
        )
        raise
