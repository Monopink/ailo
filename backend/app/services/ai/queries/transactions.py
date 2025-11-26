"""
Database transaction operations for AI services.

This module provides complex transaction operations that involve multiple
database operations and require atomicity.
"""

import secrets
import string
from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select

from models.ai import AIInstance, AIConversationItemArchive, AIRequestLog
from models.profile import Profile
from models.contact import Contact
from .updates import (
    update_instance_relationship_scores,
    set_instance_current_relationship,
    update_instance_status,
    mark_conversation_item_as_excluded,
)
from .instance_queries import get_user_id_by_qiao_id, get_instance_relationship_config
from utils.logging import get_logger
from services.ai.types import InstanceContext

logger = get_logger(__name__)


async def create_instance_with_relations(db: AsyncSession, instance_data: Dict[str, Any]) -> str:
    """
    Create an instance with associated inventory in one transaction.

    Args:
        db: Database session
        instance_data: Instance creation payload

    Returns:
        Instance qiao_id

    Raises:
        RuntimeError: If creation fails
    """
    try:
        if "typing_speed_wpm" not in instance_data:
            raise ValueError("typing_speed_wpm is required to create instance")

        creation_metadata = instance_data.get("creation_metadata")
        if creation_metadata is None:
            creation_metadata = dict(instance_data)
            creation_metadata.pop("creation_metadata", None)

        ai_instance = AIInstance(
            qiao_id=instance_data["qiao_id"],
            status=instance_data.get("status", 1),
            style_id=instance_data["style_id"],
            personality_id=instance_data["personality_id"],
            memory=instance_data.get("memory"),
            prompt_variables=instance_data.get("prompt_variables", {}),
            request_params=instance_data.get("request_params"),
            created_by=instance_data.get("created_by", 2),
            typing_speed_wpm=instance_data["typing_speed_wpm"],
            creation_metadata=creation_metadata,
        )

        db.add(ai_instance)
        await db.flush()

        profile = Profile(
            owner_qiao_id=instance_data["qiao_id"],
            owner_type=2,
            nickname=instance_data.get("nickname"),
            gender=instance_data.get("gender"),
            avatar_url=instance_data.get("avatar_url"),
            bio=instance_data.get("bio"),
            region=instance_data.get("region"),
        )
        db.add(profile)

        if instance_data.get("user_qiao_id"):
            random_chars = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))
            conv_id = f"conv_{random_chars}"

            contact = Contact(
                conv_id=conv_id,
                user_qiao_id=instance_data["user_qiao_id"],
                contact_type=2,
                contact_qiao_id=instance_data["qiao_id"],
                is_pinned=0,
                is_muted=0,
                is_blocked=0,
                is_deleted=0,
            )
            db.add(contact)

        await db.flush()

        logger.info(
            "instance_created_with_relations",
            instance_qiao_id=instance_data["qiao_id"],
            user_qiao_id=instance_data.get("user_qiao_id"),
        )

        return instance_data["qiao_id"]

    except Exception as e:
        logger.error("instance_creation_failed", error=str(e), instance_data=instance_data)
        raise RuntimeError(f"Failed to create instance with relations: {str(e)}")


async def save_ai_request_log(
    db: AsyncSession,
    instance_context: InstanceContext,
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
        instance_context: Instance context dictionary
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

        response_payload: Dict[str, Any]
        if isinstance(ai_response, dict):
            response_payload = dict(ai_response)
        else:
            response_payload = {"content": ai_response}

        llm_debug_payload: Dict[str, Any] = {}
        for key in (
            "raw_response",
            "raw_content",
            "tool_calls",
            "reasoning_content",
            "finish_reason",
            "streaming",
        ):
            value = llm_result.get(key)
            if value not in (None, {}, []):
                llm_debug_payload[key] = value

        # Include cache metadata for debugging if provided.
        for meta_key in ("cache_hit", "cache_strategy"):
            if meta_key in llm_result and llm_result[meta_key] is not None:
                llm_debug_payload[meta_key] = llm_result[meta_key]

        if llm_debug_payload:
            response_payload["__llm_response"] = llm_debug_payload

        request_log = AIRequestLog(
            instance_id=instance_context["instance_id"],
            user_id=user_id,  # ✅ FIXED: use user_id (int) not user_qiao_id (str)
            style_id=instance_context["style"]["id"],
            personality_id=instance_context["personality"]["id"],
            request_type="production",
            provider_name=llm_result.get("config_used", {}).get("provider_name"),
            model_name=llm_result.get("model"),
            llm_config_id=(llm_result.get("config_used") or {}).get("id"),
            response_id=llm_result.get("response_id"),
            cache_hit=bool(llm_result.get("cache_hit")),
            buffer_id=buffer_id,
            request=llm_result.get("request_payload", {}),
            response=response_payload,
            status=1 if llm_result.get("success") else 2,
            token_count=llm_result.get("usage", {}).get("total_tokens", 0),
            response_time=int(llm_result.get("response_time", 0) * 1000),  # Convert to ms
        )

        db.add(request_log)
        await db.flush()

        logger.debug(
            "ai_request_log_saved",
            instance_id=instance_context["instance_id"],
            user_id=user_id,
        )

    except Exception as e:
        logger.error("ai_request_log_save_failed", error=str(e), user_qiao_id=user_qiao_id, exc_info=True)
        # Don't raise - logging failure shouldn't break the conversation
        pass


async def archive_contexts_transaction(
    db: AsyncSession, contexts_to_archive: list, instance_qiao_id: str
) -> int:
    """
    Archive contexts in a transaction.

    Args:
        db: Database session
        contexts_to_archive: List of context objects to archive
        instance_qiao_id: Instance's qiao_id

    Returns:
        Number of contexts archived
    """
    try:
        archived_count = 0

        for context in contexts_to_archive:
            try:
                # Create archive entry
                archive_entry = AIConversationItemArchive(
                    instance_qiao_id=context.instance_qiao_id,
                    user_qiao_id=context.user_qiao_id,
                    role=context.role,
                    message_type=context.message_type,
                    text_content=context.text_content,
                    media_url=context.media_url,
                    media_metadata=context.media_metadata,
                    buffer_id=context.buffer_id,
                    is_excluded_from_context=int(context.is_excluded_from_context or 0),
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
                    instance_qiao_id=instance_qiao_id,
                )
                continue

        await db.flush()

        logger.info(
            "contexts_archived_in_transaction",
            instance_qiao_id=instance_qiao_id,
            archived_count=archived_count,
            total_requested=len(contexts_to_archive),
        )

        return archived_count

    except Exception as e:
        logger.error(
            "context_archiving_transaction_failed",
            error=str(e),
            instance_qiao_id=instance_qiao_id,
            contexts_count=len(contexts_to_archive),
        )
        return 0


async def archive_all_conversation_items(db: AsyncSession, user_qiao_id: str, instance_qiao_id: str) -> int:
    """
    Archive all conversation items for a user-instance pair.

    Args:
        db: Database session
        user_qiao_id: User's qiao_id
        instance_qiao_id: Instance's qiao_id

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
                    AIConversationItem.instance_qiao_id == instance_qiao_id,
                )
            )
        )
        items = list(result.scalars().all())

        if not items:
            logger.info(
                "no_conversation_items_to_archive",
                user_qiao_id=user_qiao_id,
                instance_qiao_id=instance_qiao_id,
            )
            return 0

        archived_count = await archive_contexts_transaction(db, items, instance_qiao_id)
        await db.commit()

        logger.info(
            "all_conversation_items_archived",
            user_qiao_id=user_qiao_id,
            instance_qiao_id=instance_qiao_id,
            archived_count=archived_count,
        )

        return archived_count

    except Exception as e:
        await db.rollback()
        logger.error(
            "archive_all_conversation_items_failed",
            error=str(e),
            user_qiao_id=user_qiao_id,
            instance_qiao_id=instance_qiao_id,
            exc_info=True,
        )
        raise
