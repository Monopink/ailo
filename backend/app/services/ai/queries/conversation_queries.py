"""
AI conversation item query functions.

Provides read-only helpers for retrieving buffered conversation history
stored in ai_conversation_items.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.common import ConversationItemContextStatus
from app.models.ai import AIConversationItem
from app.utils.logging import get_logger

logger = get_logger(__name__)


async def get_conversation_contexts(
    db: AsyncSession,
    instance_qiao_id: str,
    user_qiao_id: str,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """
    Return conversation items (excluding flagged content) ordered for prompt building.
    """
    try:
        query = (
            select(AIConversationItem)
            .where(
                and_(
                    AIConversationItem.user_qiao_id == user_qiao_id,
                    AIConversationItem.instance_qiao_id == instance_qiao_id,
                    AIConversationItem.is_excluded_from_context
                    == ConversationItemContextStatus.INCLUDED,
                )
            )
            .order_by(desc(AIConversationItem.created_at), desc(AIConversationItem.id))
        )

        if isinstance(limit, int) and limit > 0:
            query = query.limit(limit)

        result = await db.execute(query)
        items = list(result.scalars().all())

        formatted: list[dict[str, Any]] = []
        for item in reversed(items):
            formatted.append(_serialize_item(item))

        logger.debug(
            "conversation_items_retrieved",
            instance_qiao_id=instance_qiao_id,
            user_qiao_id=user_qiao_id,
            item_count=len(formatted),
        )

        return formatted

    except Exception as exc:
        logger.error(
            "conversation_items_query_failed",
            error=str(exc),
            instance_qiao_id=instance_qiao_id,
            user_qiao_id=user_qiao_id,
        )
        return []


async def get_conversation_history(
    db: AsyncSession,
    user_qiao_id: str,
    instance_qiao_id: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """
    Return recent conversation items (including excluded entries) for audit UIs.
    """
    try:
        result = await db.execute(
            select(AIConversationItem)
            .where(
                and_(
                    AIConversationItem.user_qiao_id == user_qiao_id,
                    AIConversationItem.instance_qiao_id == instance_qiao_id,
                )
            )
            .order_by(desc(AIConversationItem.created_at))
            .limit(limit)
        )

        items = list(result.scalars().all())
        history: list[dict[str, Any]] = []
        for item in reversed(items):
            payload = _serialize_item(item)
            payload["is_excluded_from_context"] = (
                item.is_excluded_from_context == ConversationItemContextStatus.EXCLUDED
            )
            payload["buffer_id"] = item.buffer_id
            history.append(payload)

        logger.debug(
            "conversation_history_retrieved",
            user_qiao_id=user_qiao_id,
            instance_qiao_id=instance_qiao_id,
            count=len(history),
        )

        return history

    except Exception as exc:
        logger.error(
            "conversation_history_query_failed",
            error=str(exc),
            user_qiao_id=user_qiao_id,
            instance_qiao_id=instance_qiao_id,
        )
        return []


async def get_conversation_item_by_id(db: AsyncSession, item_id: int) -> dict[str, Any] | None:
    """
    Fetch a single conversation item by ID.
    """
    try:
        result = await db.execute(
            select(AIConversationItem).where(AIConversationItem.id == item_id)
        )
        item = result.scalar_one_or_none()
        if not item:
            logger.warning("conversation_item_not_found", item_id=item_id)
            return None

        payload = _serialize_item(item)
        payload.update(
            {
                "buffer_id": item.buffer_id,
                "is_excluded_from_context": (
                    item.is_excluded_from_context == ConversationItemContextStatus.EXCLUDED
                ),
            }
        )
        return payload

    except Exception as exc:
        logger.error("conversation_item_by_id_query_failed", error=str(exc), item_id=item_id)
        return None


async def get_items_for_archiving(
    db: AsyncSession,
    instance_qiao_id: str,
    user_qiao_id: str,
    max_age_seconds: int = 604800,
    max_count: int = 100,
    archive_threshold: int | None = None,
) -> tuple[list[AIConversationItem], int]:
    """
    Determine which conversation items should be archived to cold storage.
    """
    try:
        cutoff = datetime.now(UTC) - timedelta(seconds=max_age_seconds)

        result = await db.execute(
            select(AIConversationItem)
            .where(
                and_(
                    AIConversationItem.instance_qiao_id == instance_qiao_id,
                    AIConversationItem.user_qiao_id == user_qiao_id,
                )
            )
            .order_by(desc(AIConversationItem.created_at), desc(AIConversationItem.id))
        )

        items = list(result.scalars().all())
        to_archive: list[AIConversationItem] = []

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
            instance_qiao_id=instance_qiao_id,
            user_qiao_id=user_qiao_id,
            total_items=len(items),
            to_archive=len(to_archive),
        )

        return to_archive, len(items)

    except Exception as exc:
        logger.error(
            "conversation_item_archiving_query_failed",
            error=str(exc),
            instance_qiao_id=instance_qiao_id,
            user_qiao_id=user_qiao_id,
        )
        return [], 0


def _serialize_item(item: AIConversationItem) -> dict[str, Any]:
    """Serialize ORM conversation item into dictionary form."""
    return {
        "id": item.id,
        "user_qiao_id": item.user_qiao_id,
        "instance_qiao_id": item.instance_qiao_id,
        "role": item.role,
        "message_type": item.message_type,
        "text_content": item.text_content,
        "media_url": item.media_url,
        "media_metadata": item.media_metadata,
        "created_at": item.created_at,
    }
