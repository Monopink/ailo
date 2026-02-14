"""
Conversation runtime turn-version helpers.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai import AIConversationRuntime


async def increment_ingress_version(
    db: AsyncSession,
    user_qiao_id: str,
    instance_qiao_id: str,
) -> int:
    """Increment ingress_version for CONTENT_INPUT events and return the new value."""

    runtime = await _lock_runtime_row(db, user_qiao_id, instance_qiao_id)
    runtime.ingress_version += 1
    await db.flush()
    return int(runtime.ingress_version)


async def activate_current_ingress_turn(
    db: AsyncSession,
    user_qiao_id: str,
    instance_qiao_id: str,
) -> int:
    """Set active_turn_version to ingress_version and return the active turn value."""

    runtime = await _lock_runtime_row(db, user_qiao_id, instance_qiao_id)
    runtime.active_turn_version = runtime.ingress_version
    await db.flush()
    return int(runtime.active_turn_version)


async def get_active_turn_version(
    db: AsyncSession,
    user_qiao_id: str,
    instance_qiao_id: str,
) -> int:
    """Read active_turn_version for preemption checks."""

    result = await db.execute(
        select(AIConversationRuntime.active_turn_version).where(
            AIConversationRuntime.user_qiao_id == user_qiao_id,
            AIConversationRuntime.instance_qiao_id == instance_qiao_id,
        )
    )
    value = result.scalar_one_or_none()
    return int(value) if value is not None else 0


async def is_active_turn(
    db: AsyncSession,
    user_qiao_id: str,
    instance_qiao_id: str,
    task_turn_version: int,
) -> bool:
    """Return True when the task turn is still the active processing turn."""

    current_active_turn = await get_active_turn_version(db, user_qiao_id, instance_qiao_id)
    return current_active_turn == task_turn_version


async def _lock_runtime_row(
    db: AsyncSession,
    user_qiao_id: str,
    instance_qiao_id: str,
) -> AIConversationRuntime:
    await db.execute(
        insert(AIConversationRuntime)
        .values(
            user_qiao_id=user_qiao_id,
            instance_qiao_id=instance_qiao_id,
            ingress_version=0,
            active_turn_version=0,
        )
        .on_conflict_do_nothing(
            index_elements=["user_qiao_id", "instance_qiao_id"],
        )
    )
    result = await db.execute(
        select(AIConversationRuntime)
        .where(
            AIConversationRuntime.user_qiao_id == user_qiao_id,
            AIConversationRuntime.instance_qiao_id == instance_qiao_id,
        )
        .with_for_update()
    )
    return result.scalar_one()
