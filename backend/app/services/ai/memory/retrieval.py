"""Memory retrieval helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai.memory import AIInstanceMemory
from app.services.ai.memory.config import get_memory_limits
from app.type_defs import InstanceContext
from app.utils.logging import get_logger

logger = get_logger(__name__)

MIN_IMPORTANCE = 1
RECENT_LIFETIME_MULTIPLIER = 10
FUZZY_CLEAR_THRESHOLD = 0.75
FUZZY_MODERATE_THRESHOLD = 0.5
FUZZY_LIGHT_THRESHOLD = 0.25


async def build_memory_prompt(db: AsyncSession, context: InstanceContext) -> str:
    """Fetch memories for an instance and format them for the system prompt."""

    limits = await get_memory_limits(db, context)
    user_qiao_id = context["user_qiao_id"]
    instance_qiao_id = context["instance_qiao_id"]
    now = datetime.now(UTC)

    core_memories = await _fetch_memories(
        db,
        user_qiao_id=user_qiao_id,
        instance_qiao_id=instance_qiao_id,
        memory_type="core",
        limit=limits.get("core", 0),
        now=now,
    )
    recent_memories = await _fetch_memories(
        db,
        user_qiao_id=user_qiao_id,
        instance_qiao_id=instance_qiao_id,
        memory_type="recent",
        limit=limits.get("recent", 0),
        now=now,
    )

    lines: list[str] = []
    if core_memories:
        lines.append("## 关于用户的记忆\n")
        lines.append("核心记忆：")
        for mem in core_memories:
            lines.append(f"- {mem.content}")
        lines.append("")

    if recent_memories:
        if not lines:
            lines.append("## 关于用户的记忆\n")
        lines.append("近期记忆（按确定性排序）：")
        for mem in recent_memories:
            label = _fuzzy_label(mem, now)
            lines.append(f"- {label} {mem.content}")
        lines.append("")
        lines.append(
            '注意：对于标记为"较模糊"及以上的记忆，在对话中可以用"我记得"、"好像"等词自然表达不确定性。'
        )

    return "\n".join(lines).strip()


async def _fetch_memories(
    db: AsyncSession,
    *,
    user_qiao_id: str,
    instance_qiao_id: str,
    memory_type: str,
    limit: int,
    now: datetime,
) -> list[AIInstanceMemory]:
    if limit <= 0:
        return []

    stmt = (
        select(AIInstanceMemory)
        .where(
            AIInstanceMemory.user_qiao_id == user_qiao_id,
            AIInstanceMemory.instance_qiao_id == instance_qiao_id,
            AIInstanceMemory.status == 1,
            AIInstanceMemory.memory_type == memory_type,
        )
        .order_by(AIInstanceMemory.importance.desc(), AIInstanceMemory.created_at.desc())
        .limit(limit)
    )

    if memory_type == "recent":
        stmt = stmt.where(
            AIInstanceMemory.expires_at.is_(None) | (AIInstanceMemory.expires_at > now),
        )

    result = await db.execute(stmt)
    return list(result.scalars().all())


def _fuzzy_label(memory: AIInstanceMemory, now: datetime) -> str:
    base_time = memory.refreshed_at or memory.created_at or now
    lifetime_days = max(int(memory.importance), MIN_IMPORTANCE) * RECENT_LIFETIME_MULTIPLIER
    elapsed_days = (now - base_time).total_seconds() / 86400
    remaining = max(lifetime_days - elapsed_days, 0)
    ratio = remaining / lifetime_days if lifetime_days > 0 else 0

    if ratio >= FUZZY_CLEAR_THRESHOLD:
        return "[清晰]"
    if ratio >= FUZZY_MODERATE_THRESHOLD:
        return "[较模糊]"
    if ratio >= FUZZY_LIGHT_THRESHOLD:
        return "[很模糊]"
    return "[极模糊]"
