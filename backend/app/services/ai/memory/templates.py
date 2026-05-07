"""Template memory seeding helpers."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai import AIInstance
from app.models.ai.memory import AITemplateMemory
from app.services.ai.memory.memory_policy_service import (
    ORIGIN_TEMPLATE,
    archive_recent_over_limit,
    lock_instance_for_memory_write,
    upsert_memory_with_policy,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)


async def copy_template_memories_to_instance(
    db: AsyncSession,
    *,
    template_id: int,
    instance: AIInstance,
) -> int:
    """Copy template memories into an instance-scoped memory table."""
    try:
        result = await db.execute(
            select(AITemplateMemory)
            .where(AITemplateMemory.template_id == template_id)
            .order_by(AITemplateMemory.display_order)
        )
        template_memories = list(result.scalars().all())

        if not template_memories:
            logger.debug(
                "template_memories_empty",
                template_id=template_id,
                instance_id=instance.id,
            )
            return 0

        locked_instance = await lock_instance_for_memory_write(db, instance.id)

        for template_memory in template_memories:
            await upsert_memory_with_policy(
                db,
                instance=locked_instance,
                memory_type=template_memory.memory_type,
                content=template_memory.content,
                importance=template_memory.importance,
                origin=ORIGIN_TEMPLATE,
                source_message_id=None,
            )

        await archive_recent_over_limit(
            db,
            instance=locked_instance,
            trigger="template_copy",
        )
        await db.flush()

        logger.debug(
            "template_memories_copied",
            template_id=template_id,
            instance_id=instance.id,
            copied_count=len(template_memories),
        )
        return len(template_memories)
    except Exception as exc:
        logger.error(
            "template_memory_copy_failed",
            error=str(exc),
            template_id=template_id,
            instance_id=getattr(instance, "id", None),
            exc_info=True,
        )
        raise
