"""
AI conversation item query functions.

Provides read-only helpers for retrieving buffered conversation history
stored in ai_conversation_items.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ConversationItemContextStatus
from app.models.ai import AIConversationItem
from app.utils.logging import get_logger

logger = get_logger(__name__)


async def get_conversation_contexts(
    db: AsyncSession,
    instance_qiao_id: str,
    user_qiao_id: str,
    limit: int | None = None,
    context_window_start: datetime | None = None,
) -> list[dict[str, Any]]:
    """
    Return conversation items (excluding flagged content) ordered for prompt building.
    """
    try:
        conditions = [
            AIConversationItem.user_qiao_id == user_qiao_id,
            AIConversationItem.instance_qiao_id == instance_qiao_id,
            AIConversationItem.is_excluded_from_context == ConversationItemContextStatus.INCLUDED,
        ]
        if context_window_start is not None:
            conditions.append(AIConversationItem.created_at >= context_window_start)

        query = (
            select(AIConversationItem)
            .where(and_(*conditions))
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
