"""
Database transaction operations for AI services.

This module provides complex transaction operations that involve multiple
database operations and require atomicity.
"""

from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from models.ai import AICharacter, AIContextArchive, AIRequestLog
from models.profile import Profile
from models.contact import Contact
from enums import AIContextRole
from .updates import (
    save_context_entry,
    update_relationship_scores,
    set_current_relationship,
    mark_context_as_attack,
    update_character_status,
    finalize_context_if_locked,
)
from .character_queries import get_user_id_by_qiao_id
from .template_queries import get_profile_template_by_id, get_character_template_by_id
from utils.logging import get_logger

logger = get_logger(__name__)


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


async def save_conversation_result(
    db: AsyncSession,
    user_qiao_id: str,
    character_qiao_id: str,
    character_info: Dict[str, Any],
    ai_response: Dict[str, Any],
    new_scores: Optional[Dict[str, int]],
    memory_operations: Optional[List[Dict]],
    llm_result: Dict[str, Any],
    locked_context_id: Optional[int],
) -> Dict[str, Any]:
    """
    Save all conversation results in a single atomic transaction.

    This function ensures atomicity - either all operations succeed or all fail.

    Args:
        db: Database session
        user_qiao_id: User's qiao_id
        character_qiao_id: Character's qiao_id
        character_info: Character information dictionary
        ai_response: AI response dictionary
        new_scores: New relationship scores (dimension_name -> score)
        memory_operations: Memory operations to process
        llm_result: LLM result with usage info
        locked_context_id: Locked context ID (if any)

    Returns:
        Dictionary with success status and context_id

    Raises:
        Exception: If any operation fails (triggers rollback)
    """
    try:
        # 1. Update relationship scores
        if new_scores:
            await update_relationship_scores(db, character_info["character_id"], new_scores)

            # Re-evaluate relationship after score update
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

        # 2. Process memory operations
        if memory_operations:
            from ..conversation_memory import process_memory_operations

            await process_memory_operations(db, character_qiao_id, memory_operations)

        # 3. Handle attack detection
        if ai_response.get("attack_detected") and locked_context_id:
            await mark_context_as_attack(db, locked_context_id)

        # 4. Handle blocking
        if ai_response.get("should_block"):
            await update_character_status(db, character_qiao_id, status=3)  # blocked

        # 5. Send response messages and save to contexts
        if ai_response.get("should_reply"):
            from services.message.outbound.sender import send_message
            from crud.contact import contact as contact_crud
            from enums import MessageType

            outgoing_messages = ai_response.get("outgoing_messages", [])
            for message in outgoing_messages:
                # Get contact for conv_id
                contact = await contact_crud.get_user_contact(
                    db, user_qiao_id=user_qiao_id, contact_qiao_id=character_qiao_id
                )

                if contact:
                    # Send message
                    await send_message(
                        db=db,
                        from_qiao_id=character_qiao_id,
                        to_qiao_id=user_qiao_id,
                        conv_id=contact.conv_id,
                        content=message,
                        message_type=MessageType.TEXT,
                    )

                    # Save AI response to ai_contexts table
                    context_data = {
                        "character_qiao_id": character_qiao_id,
                        "user_qiao_id": user_qiao_id,
                        "role": AIContextRole.ASSISTANT,
                        "content": message,
                    }
                    context_id = await save_context_entry(db, context_data)

                    if not context_id:
                        logger.error(
                            "failed_to_save_ai_response_to_context",
                            character_qiao_id=character_qiao_id,
                            user_qiao_id=user_qiao_id,
                        )
                else:
                    logger.error(
                        "contact_not_found_for_sending",
                        user_qiao_id=user_qiao_id,
                        character_qiao_id=character_qiao_id,
                    )

        # 6. Save AI request log (NEW - fixes missing logging issue)
        await _save_ai_request_log(
            db=db,
            character_info=character_info,
            user_qiao_id=user_qiao_id,
            ai_response=ai_response,
            llm_result=llm_result,
        )

        # 7. Update context status to COMPLETE
        if locked_context_id:
            await finalize_context_if_locked(db, locked_context_id)

        # Commit transaction
        await db.commit()

        logger.info(
            "conversation_result_saved",
            user_qiao_id=user_qiao_id,
            character_qiao_id=character_qiao_id,
            context_id=locked_context_id,
        )

        return {
            "success": True,
            "context_id": locked_context_id,
        }

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


async def _save_ai_request_log(
    db: AsyncSession,
    character_info: Dict[str, Any],
    user_qiao_id: str,
    ai_response: Dict[str, Any],
    llm_result: Dict[str, Any],
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
                archive_entry = AIContextArchive(
                    character_qiao_id=context.character_qiao_id,
                    user_qiao_id=context.user_qiao_id,
                    role=context.role,
                    content=context.content,
                    position=context.position,
                    token_count=context.token_count,
                    is_attack=context.is_attack,
                    aggregate_state=context.aggregate_state,
                    created_at=context.created_at,
                    updated_at=context.updated_at,
                )

                db.add(archive_entry)

                # Delete from main table
                await db.delete(context)
                archived_count += 1

            except Exception as e:
                logger.error(
                    "single_context_archive_failed",
                    error=str(e),
                    context_id=context.id,
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
