"""
AI Context CRUD operations.

This module provides both standard CRUD operations and complex queries
for AI conversation context management.
"""

from typing import List
from sqlalchemy import select, and_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from crud.base import CRUDBase
from models.ai import AIContext, AIContextArchive
from schemas.ai import AIContextCreate, AIContextUpdate
from utils.logging import get_logger

logger = get_logger(__name__)


class CRUDAIContext(CRUDBase[AIContext, AIContextCreate, AIContextUpdate]):
    """AI Context CRUD operations with complex queries."""

    # Complex queries moved to services/ai/data layer for better separation of concerns

    async def get_contexts_for_archiving(
        self, db: AsyncSession, *, character_qiao_id: str, max_age_days: int = 30, max_count: int = 100
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
            cutoff_date = datetime.now() - timedelta(days=max_age_days)

            # Get all done contexts for this character
            result = await db.execute(
                select(AIContext)
                .where(
                    and_(
                        AIContext.character_qiao_id == character_qiao_id,
                        AIContext.reply_status == 3,  # done
                    )
                )
                .order_by(desc(AIContext.created_at))
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

    async def archive_contexts_batch(
        self, db: AsyncSession, *, contexts_to_archive: List[AIContext]
    ) -> int:
        """
        Archive contexts in a transaction.

        Args:
            db: Database session
            contexts_to_archive: List of context objects to archive

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
                    logger.error("single_context_archive_failed", error=str(e), context_id=context.id)
                    continue

            await db.flush()

            logger.info(
                "contexts_archived_in_batch",
                archived_count=archived_count,
                total_requested=len(contexts_to_archive),
            )

            return archived_count

        except Exception as e:
            logger.error(
                "context_archiving_batch_failed", error=str(e), contexts_count=len(contexts_to_archive)
            )
            return 0

    async def get_recent_contexts_count(
        self, db: AsyncSession, *, character_qiao_id: str, hours: int = 24
    ) -> int:
        """
        Get count of recent contexts for rate limiting.

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
                    and_(
                        AIContext.character_qiao_id == character_qiao_id,
                        AIContext.created_at >= cutoff_time,
                    )
                )
            )

            count = result.scalar() or 0

            logger.debug(
                "recent_contexts_count_retrieved",
                character_qiao_id=character_qiao_id,
                hours=hours,
                count=count,
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


ai_context = CRUDAIContext(AIContext)
