"""Template memory seeding helpers."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai import AIInstance
from app.models.ai.memory import AIInstanceMemory, AITemplateMemory
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

        for template_memory in template_memories:
            memory = AIInstanceMemory(
                instance_id=instance.id,
                instance_qiao_id=instance.qiao_id,
                user_id=instance.user_id,
                user_qiao_id=instance.user_qiao_id,
                memory_type=template_memory.memory_type,
                content=template_memory.content,
                importance=template_memory.importance,
                status=1,
            )
            db.add(memory)

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
