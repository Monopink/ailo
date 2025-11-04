"""
AI conversation context query functions.

This module provides conversation context and history query functions
with clear separation of concerns and pure function design.
"""

from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, func
from datetime import datetime, timedelta

from models.ai import AIContext
from enums import AIAggregateState, AIContextRole
from utils.logging import get_logger

logger = get_logger(__name__)


async def get_conversation_contexts(
    db: AsyncSession,
    character_qiao_id: str,
    user_qiao_id: str,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Get conversation contexts for prompt building.

    Args:
        db: Database session
        character_qiao_id: Character's qiao_id
        user_qiao_id: User's qiao_id
        limit: Maximum number of contexts to return

    Returns:
        List of context dictionaries with role and content
    """
    try:
        # Only user role requires COMPLETE state; assistant/system do not use aggregate_state
        # Build base query
        query = (
            select(AIContext)
            .where(
                and_(
                    AIContext.user_qiao_id == user_qiao_id,
                    AIContext.character_qiao_id == character_qiao_id,
                    or_(
                        and_(
                            AIContext.role == AIContextRole.USER,
                            AIContext.aggregate_state == AIAggregateState.COMPLETE,
                        ),
                        AIContext.role != AIContextRole.USER,
                    ),
                )
            )
            .order_by(desc(AIContext.created_at), desc(AIContext.id))
        )

        # Apply limit only when specified
        if isinstance(limit, int) and limit > 0:
            query = query.limit(limit)

        result = await db.execute(query)

        contexts = result.scalars().all()

        # Convert to dictionaries and reverse order (oldest first for conversation flow)
        context_list = []
        for context in reversed(contexts):
            context_list.append(
                {
                    "id": context.id,
                    "role": context.role,
                    "content": context.content,
                    "created_at": context.created_at,
                }
            )

        logger.debug(
            "conversation_contexts_retrieved",
            character_qiao_id=character_qiao_id,
            user_qiao_id=user_qiao_id,
            contexts_count=len(context_list),
        )

        return context_list

    except Exception as e:
        logger.error(
            "conversation_contexts_query_failed",
            error=str(e),
            character_qiao_id=character_qiao_id,
            user_qiao_id=user_qiao_id,
        )
        return []


async def get_conversation_history(
    db: AsyncSession, user_qiao_id: str, character_qiao_id: str, limit: int = 20
) -> List[Dict[str, Any]]:
    """
    Get conversation history between user and character.

    Args:
        db: Database session
        user_qiao_id: User's qiao_id
        character_qiao_id: Character's qiao_id
        limit: Maximum number of context entries to return

    Returns:
        List of context dictionaries
    """
    try:
        # Only user role requires COMPLETE state; assistant/system do not use aggregate_state
        result = await db.execute(
            select(AIContext)
            .where(
                and_(
                    AIContext.user_qiao_id == user_qiao_id,
                    AIContext.character_qiao_id == character_qiao_id,
                    or_(
                        and_(
                            AIContext.role == AIContextRole.USER,
                            AIContext.aggregate_state == AIAggregateState.COMPLETE,
                        ),
                        AIContext.role != AIContextRole.USER,
                    ),
                )
            )
            .order_by(desc(AIContext.created_at))
            .limit(limit)
        )

        contexts = result.scalars().all()

        # Convert to dictionaries and reverse order (oldest first)
        history = []
        for context in reversed(contexts):
            history.append(
                {
                    "id": context.id,
                    "role": context.role,
                    "content": context.content,
                    "created_at": context.created_at,
                    "is_attack": context.is_attack,
                }
            )

        logger.debug(
            "conversation_history_retrieved",
            user_qiao_id=user_qiao_id,
            character_qiao_id=character_qiao_id,
            count=len(history),
        )

        return history

    except Exception as e:
        logger.error(
            "conversation_history_query_failed",
            error=str(e),
            user_qiao_id=user_qiao_id,
            character_qiao_id=character_qiao_id,
        )
        return []


async def get_context_by_id(db: AsyncSession, context_id: int) -> Optional[Dict[str, Any]]:
    """
    Get context by ID.

    Args:
        db: Database session
        context_id: Context ID

    Returns:
        Context dictionary or None if not found
    """
    try:
        result = await db.execute(select(AIContext).where(AIContext.id == context_id))

        context = result.scalar_one_or_none()
        if not context:
            logger.warning("context_not_found", context_id=context_id)
            return None

        return {
            "id": context.id,
            "character_qiao_id": context.character_qiao_id,
            "user_qiao_id": context.user_qiao_id,
            "role": context.role,
            "content": context.content,
            "aggregate_state": context.aggregate_state,
            "is_attack": context.is_attack,
            "created_at": context.created_at,
        }

    except Exception as e:
        logger.error("context_by_id_query_failed", error=str(e), context_id=context_id)
        return None


async def get_contexts_for_archiving(
    db: AsyncSession,
    character_qiao_id: str,
    user_qiao_id: str,
    max_age_seconds: int = 604800,
    max_count: int = 100,
) -> List[AIContext]:
    """
    Get contexts that should be archived.

    Args:
        db: Database session
        character_qiao_id: Character's qiao_id
        max_age_days: Maximum age in days before archiving
        max_count: Maximum number of contexts to keep

    Returns:
        List of contexts to archive
    """
    try:
        from datetime import timezone

        # Compute cutoff by seconds for consistency with system config convention
        cutoff_date = datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)

        # Get all done contexts for this character
        result = await db.execute(
            select(AIContext)
            .where(
                and_(
                    AIContext.character_qiao_id == character_qiao_id,
                    AIContext.user_qiao_id == user_qiao_id,
                    AIContext.aggregate_state == 3,  # done
                )
            )
            .order_by(desc(AIContext.created_at), desc(AIContext.id))
        )

        all_contexts = result.scalars().all()

        contexts_to_archive = []

        # Archive contexts older than cutoff date
        for context in all_contexts:
            if context.created_at < cutoff_date:
                contexts_to_archive.append(context)

        # Archive excess contexts (keep only max_count newest)
        if len(all_contexts) > max_count:
            excess_contexts = all_contexts[max_count:]
            for context in excess_contexts:
                if context not in contexts_to_archive:
                    contexts_to_archive.append(context)

        logger.debug(
            "contexts_for_archiving_identified",
            character_qiao_id=character_qiao_id,
            total_contexts=len(all_contexts),
            to_archive=len(contexts_to_archive),
        )

        return contexts_to_archive

    except Exception as e:
        logger.error(
            "contexts_for_archiving_query_failed", error=str(e), character_qiao_id=character_qiao_id
        )
        return []


async def get_recent_contexts_count(db: AsyncSession, character_qiao_id: str, hours: int = 24) -> int:
    """
    Get count of recent contexts for a character.

    Args:
        db: Database session
        character_qiao_id: Character's qiao_id
        hours: Number of hours to look back

    Returns:
        Count of recent contexts
    """
    try:
        cutoff_time = datetime.now() - timedelta(hours=hours)

        result = await db.execute(
            select(func.count(AIContext.id)).where(
                and_(AIContext.character_qiao_id == character_qiao_id, AIContext.created_at >= cutoff_time)
            )
        )

        count = result.scalar() or 0

        logger.debug(
            "recent_contexts_count_retrieved", character_qiao_id=character_qiao_id, hours=hours, count=count
        )

        return count

    except Exception as e:
        logger.error(
            "recent_contexts_count_query_failed",
            error=str(e),
            character_qiao_id=character_qiao_id,
            hours=hours,
        )
        return 0
