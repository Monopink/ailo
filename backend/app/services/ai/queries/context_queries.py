"""
AI conversation item query functions.

Provides read-only helpers for retrieving buffered conversation history
stored in ai_conversation_items.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.ai import AIConversationItem
from utils.logging import get_logger

logger = get_logger(__name__)


async def get_conversation_contexts(
    db: AsyncSession,
    character_qiao_id: str,
    user_qiao_id: str,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Return conversation items (excluding flagged content) ordered for prompt building.
    """
    try:
        query = (
            select(AIConversationItem)
            .where(
                and_(
                    AIConversationItem.user_qiao_id == user_qiao_id,
                    AIConversationItem.character_qiao_id == character_qiao_id,
                    AIConversationItem.is_excluded_from_context.is_(False),
                )
            )
            .order_by(desc(AIConversationItem.created_at), desc(AIConversationItem.id))
        )

        if isinstance(limit, int) and limit > 0:
            query = query.limit(limit)

        result = await db.execute(query)
        items = list(result.scalars().all())

        formatted: List[Dict[str, Any]] = []
        for item in reversed(items):
            formatted.append(
                {
                    "id": item.id,
                    "role": item.role,
                    "content": item.content,
                    "content_preview": item.content_preview,
                    "created_at": item.created_at,
                }
            )

        logger.debug(
            "conversation_items_retrieved",
            character_qiao_id=character_qiao_id,
            user_qiao_id=user_qiao_id,
            item_count=len(formatted),
        )

        return formatted

    except Exception as exc:
        logger.error(
            "conversation_items_query_failed",
            error=str(exc),
            character_qiao_id=character_qiao_id,
            user_qiao_id=user_qiao_id,
        )
        return []


async def get_conversation_history(
    db: AsyncSession,
    user_qiao_id: str,
    character_qiao_id: str,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    Return recent conversation items (including excluded entries) for audit UIs.
    """
    try:
        result = await db.execute(
            select(AIConversationItem)
            .where(
                and_(
                    AIConversationItem.user_qiao_id == user_qiao_id,
                    AIConversationItem.character_qiao_id == character_qiao_id,
                )
            )
            .order_by(desc(AIConversationItem.created_at))
            .limit(limit)
        )

        items = list(result.scalars().all())
        history: List[Dict[str, Any]] = []
        for item in reversed(items):
            history.append(
                {
                    "id": item.id,
                    "role": item.role,
                    "content": item.content,
                    "content_preview": item.content_preview,
                    "created_at": item.created_at,
                    "is_excluded_from_context": item.is_excluded_from_context,
                    "buffer_id": item.buffer_id,
                    "response_id": item.response_id,
                }
            )

        logger.debug(
            "conversation_history_retrieved",
            user_qiao_id=user_qiao_id,
            character_qiao_id=character_qiao_id,
            count=len(history),
        )

        return history

    except Exception as exc:
        logger.error(
            "conversation_history_query_failed",
            error=str(exc),
            user_qiao_id=user_qiao_id,
            character_qiao_id=character_qiao_id,
        )
        return []


async def get_conversation_item_by_id(db: AsyncSession, item_id: int) -> Optional[Dict[str, Any]]:
    """
    Fetch a single conversation item by ID.
    """
    try:
        result = await db.execute(select(AIConversationItem).where(AIConversationItem.id == item_id))
        item = result.scalar_one_or_none()
        if not item:
            logger.warning("conversation_item_not_found", item_id=item_id)
            return None

        return {
            "id": item.id,
            "user_qiao_id": item.user_qiao_id,
            "character_qiao_id": item.character_qiao_id,
            "role": item.role,
            "content": item.content,
            "content_preview": item.content_preview,
            "buffer_id": item.buffer_id,
            "response_id": item.response_id,
            "is_excluded_from_context": item.is_excluded_from_context,
            "created_at": item.created_at,
        }

    except Exception as exc:
        logger.error("conversation_item_by_id_query_failed", error=str(exc), item_id=item_id)
        return None


async def get_items_for_archiving(
    db: AsyncSession,
    character_qiao_id: str,
    user_qiao_id: str,
    max_age_seconds: int = 604800,
    max_count: int = 100,
    archive_threshold: Optional[int] = None,
) -> Tuple[List[AIConversationItem], int]:
    """
    Determine which conversation items should be archived to cold storage.
    """
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)

        result = await db.execute(
            select(AIConversationItem)
            .where(
                and_(
                    AIConversationItem.character_qiao_id == character_qiao_id,
                    AIConversationItem.user_qiao_id == user_qiao_id,
                )
            )
            .order_by(desc(AIConversationItem.created_at), desc(AIConversationItem.id))
        )

        items = list(result.scalars().all())
        to_archive: List[AIConversationItem] = []

        for item in items:
            if item.created_at < cutoff:
                to_archive.append(item)

        overflow_enabled = archive_threshold is None or len(items) >= archive_threshold
        if overflow_enabled and len(items) > max_count:
            excess = items[max_count:]
            for item in excess:
                if item not in to_archive:
                    to_archive.append(item)

        logger.debug(
            "conversation_items_for_archiving_identified",
            character_qiao_id=character_qiao_id,
            user_qiao_id=user_qiao_id,
            total_items=len(items),
            to_archive=len(to_archive),
        )

        return to_archive, len(items)

    except Exception as exc:
        logger.error(
            "conversation_item_archiving_query_failed",
            error=str(exc),
            character_qiao_id=character_qiao_id,
            user_qiao_id=user_qiao_id,
        )
        return [], 0
