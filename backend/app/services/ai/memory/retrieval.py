"""Memory retrieval helpers."""

from __future__ import annotations

import math
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai.memory import AIInstanceMemory
from app.services.ai.memory.config import get_memory_budget_tokens, get_memory_limits
from app.services.ai.memory.memory_policy_service import (
    compute_recent_utility,
    estimate_memory_tokens,
)
from app.type_defs import InstanceContext
from app.utils.logging import get_logger

logger = get_logger(__name__)


async def build_memory_prompt(db: AsyncSession, context: InstanceContext) -> str:
    """Fetch memories for an instance and format them for the system prompt."""

    limits = await get_memory_limits(db, context)
    budget_tokens = await get_memory_budget_tokens(db, context)
    hard_limit_tokens = math.floor(float(budget_tokens) * 1.15)

    user_qiao_id = context["user_qiao_id"]
    instance_qiao_id = context["instance_qiao_id"]
    now = datetime.now(UTC)

    core_candidates = await _fetch_core_candidates(
        db,
        user_qiao_id=user_qiao_id,
        instance_qiao_id=instance_qiao_id,
    )
    recent_candidates = await _fetch_recent_candidates(
        db,
        user_qiao_id=user_qiao_id,
        instance_qiao_id=instance_qiao_id,
    )

    selected_core: list[AIInstanceMemory] = []
    selected_recent: list[AIInstanceMemory] = []
    token_total = 0
    soft_budget_exceeded = False

    for memory in core_candidates:
        if len(selected_core) >= int(limits.get("core", 0)):
            break
        estimate = estimate_memory_tokens(memory.content)
        if token_total + estimate > hard_limit_tokens and selected_core:
            soft_budget_exceeded = True
            break
        selected_core.append(memory)
        token_total += estimate

    if core_candidates and not selected_core:
        selected_core.append(core_candidates[0])
        token_total += estimate_memory_tokens(core_candidates[0].content)

    ordered_recent = sorted(
        recent_candidates,
        key=lambda item: (
            compute_recent_utility(item, now),
            int(item.importance),
            int(item.source_strength),
            int(item.reinforce_count),
            item.updated_at or item.created_at or now,
            int(item.id),
        ),
        reverse=True,
    )

    for memory in ordered_recent:
        if len(selected_recent) >= int(limits.get("recent", 0)):
            break
        estimate = estimate_memory_tokens(memory.content)
        if token_total + estimate > hard_limit_tokens:
            soft_budget_exceeded = True
            continue
        selected_recent.append(memory)
        token_total += estimate

    if soft_budget_exceeded:
        logger.info(
            "memory_soft_budget_exceed_count",
            instance_qiao_id=instance_qiao_id,
            hard_limit_tokens=hard_limit_tokens,
            used_tokens=token_total,
        )

    logger.info(
        "memory_prompt_tokens",
        instance_qiao_id=instance_qiao_id,
        prompt_tokens=token_total,
        budget_tokens=budget_tokens,
        hard_limit_tokens=hard_limit_tokens,
    )

    lines: list[str] = []
    if selected_core:
        lines.append("## 关于用户的记忆\n")
        lines.append(
            "规则：每条记忆都包含 id；refresh_ids 只能从“近期记忆”的 id 中选择（每轮 1-2 条）；"
            "id 仅用于内部操作，不得在对用户消息中提及。"
        )
        lines.append("核心记忆：")
        for mem in selected_core:
            lines.append(f"- [id:{mem.id}] {mem.content}")
        lines.append("")

    if selected_recent:
        if not lines:
            lines.append("## 关于用户的记忆\n")
            lines.append(
                "规则：每条记忆都包含 id；refresh_ids 只能从“近期记忆”的 id 中选择（每轮 1-2 条）；"
                "id 仅用于内部操作，不得在对用户消息中提及。"
            )
        lines.append("近期记忆：")
        for mem in selected_recent:
            lines.append(f"- [id:{mem.id}] {mem.content}")

    return "\n".join(lines).strip()


async def _fetch_core_candidates(
    db: AsyncSession,
    *,
    user_qiao_id: str,
    instance_qiao_id: str,
) -> list[AIInstanceMemory]:
    stmt = (
        select(AIInstanceMemory)
        .where(
            AIInstanceMemory.user_qiao_id == user_qiao_id,
            AIInstanceMemory.instance_qiao_id == instance_qiao_id,
            AIInstanceMemory.status == 1,
            AIInstanceMemory.memory_type == "core",
        )
        .order_by(
            AIInstanceMemory.source_strength.desc(),
            AIInstanceMemory.importance.desc(),
            AIInstanceMemory.reinforce_count.desc(),
            AIInstanceMemory.updated_at.desc(),
            AIInstanceMemory.id.desc(),
        )
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def _fetch_recent_candidates(
    db: AsyncSession,
    *,
    user_qiao_id: str,
    instance_qiao_id: str,
) -> list[AIInstanceMemory]:
    stmt = (
        select(AIInstanceMemory)
        .where(
            AIInstanceMemory.user_qiao_id == user_qiao_id,
            AIInstanceMemory.instance_qiao_id == instance_qiao_id,
            AIInstanceMemory.status == 1,
            AIInstanceMemory.memory_type == "recent",
        )
        .order_by(
            AIInstanceMemory.updated_at.desc(),
            AIInstanceMemory.id.desc(),
        )
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
