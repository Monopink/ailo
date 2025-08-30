"""
Database transaction operations for AI services.

This module provides complex transaction operations that involve multiple
database operations and require atomicity.
"""

from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from models.ai import AICharacter, AIContextArchive
from models.profile import Profile
from models.contact import Contact
from .mutations import save_context_entry, update_relationship_scores, save_ai_response
from .template_queries import get_profile_template_by_id, get_info_template_by_id
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
            score_offset_algorithm=character_data.get("score_offset_algorithm"),
            score_offset_coefficient=character_data.get("score_offset_coefficient"),
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
            from utils.snowflake import generate_snowflake_id

            contact = Contact(
                conv_id=f"conv_{generate_snowflake_id()}",
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


async def process_conversation_transaction(db: AsyncSession, conversation_data: Dict[str, Any]) -> bool:
    """
    Process complete conversation transaction (context + response + scores).

    Args:
        db: Database session
        conversation_data: Complete conversation data

    Returns:
        True if successful, False otherwise
    """
    try:
        # Save context entry
        context_id = await save_context_entry(db, conversation_data["context"])

        # Update relationship scores if provided
        if conversation_data.get("scores"):
            await update_relationship_scores(
                db,
                conversation_data["character_id"],
                conversation_data["scores"],
            )

        # Save AI response
        response_data = conversation_data.get("response", {})
        response_data["context_id"] = context_id
        await save_ai_response(db, response_data)

        await db.commit()

        logger.info(
            "conversation_transaction_completed",
            context_id=context_id,
            user_qiao_id=conversation_data["user_qiao_id"],
            character_id=conversation_data["character_id"],
        )

        return True

    except Exception as e:
        await db.rollback()
        logger.error("conversation_transaction_failed", error=str(e), conversation_data=conversation_data)
        # Non-fatal error: log and return False
        return False


async def cleanup_single_use_templates(
    db: AsyncSession, profile_template_id: int, info_template_id: int
) -> None:
    """
    Clean up single-use templates after character creation.

    Args:
        db: Database session
        profile_template_id: Profile template ID
        info_template_id: Info template ID
    """
    try:
        # Check and delete profile template if not reusable
        profile_template = await get_profile_template_by_id(db, profile_template_id)

        if profile_template and not profile_template.is_reusable:
            await db.delete(profile_template)
            logger.debug("single_use_profile_template_deleted", template_id=profile_template_id)

        # Check and delete info template if not reusable
        info_template = await get_info_template_by_id(db, info_template_id)

        if info_template and not info_template.is_reusable:
            await db.delete(info_template)
            logger.debug("single_use_info_template_deleted", template_id=info_template_id)

        await db.flush()

    except Exception as e:
        logger.error(
            "template_cleanup_failed",
            error=str(e),
            profile_template_id=profile_template_id,
            info_template_id=info_template_id,
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
                    source_type=context.source_type,
                    context_metadata=context.context_metadata,
                    position=context.position,
                    token_count=context.token_count,
                    is_attack=context.is_attack,
                    reply_status=context.reply_status,
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
