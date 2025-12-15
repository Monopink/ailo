"""
Conversation context archiving service.

Manages the lifecycle of ai_conversation_items by archiving old
contexts to ai_conversation_items_archive based on configured policies.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.config import config_service
from app.utils.logging import get_logger

from .queries import get_items_for_archiving
from .queries.transactions import archive_contexts_transaction

logger = get_logger(__name__)


async def archive_old_contexts(db: AsyncSession, user_qiao_id: str, instance_qiao_id: str) -> int:
    """
    Archive old conversation items to ai_conversation_items_archive table.

    Args:
        db: Database session
        user_qiao_id: User's qiao_id
        instance_qiao_id: Instance's qiao_id

    Returns:
        Number of contexts archived
    """
    archived_count = 0
    try:
        # Keep archive retention readable (config stored in days)
        # but convert to seconds for queries.
        archive_time_days = await config_service.get_int(db, "ai_conversation_archive_time_days")
        archive_time_seconds = archive_time_days * 86400
        archive_max_count = await config_service.get_int(db, "ai_conversation_archive_max_count")
        archive_min_count = await config_service.get_int(db, "ai_conversation_archive_min_count")
        archive_threshold = await config_service.get_int(db, "ai_conversation_archive_threshold")

        items_to_archive, total_count = await get_items_for_archiving(
            db,
            instance_qiao_id=instance_qiao_id,
            user_qiao_id=user_qiao_id,
            max_age_seconds=int(archive_time_seconds),
            max_count=int(archive_max_count),
            archive_threshold=int(archive_threshold),
        )

        if total_count <= archive_min_count:
            logger.debug(
                "no_contexts_to_archive",
                instance_qiao_id=instance_qiao_id,
                user_qiao_id=user_qiao_id,
                reason="below_min_count",
            )
        elif not items_to_archive:
            logger.debug(
                "no_contexts_to_archive",
                instance_qiao_id=instance_qiao_id,
                user_qiao_id=user_qiao_id,
                reason="no_candidates",
            )
        else:
            archived_count = await archive_contexts_transaction(
                db, contexts_to_archive=items_to_archive, instance_qiao_id=instance_qiao_id
            )

            logger.info(
                "contexts_archived",
                instance_qiao_id=instance_qiao_id,
                user_qiao_id=user_qiao_id,
                archived_count=archived_count,
                total_contexts=len(items_to_archive),
            )

    except Exception as e:
        logger.error(
            "context_archiving_failed",
            error=str(e),
            instance_qiao_id=instance_qiao_id,
            user_qiao_id=user_qiao_id,
        )
        archived_count = 0

    return archived_count
