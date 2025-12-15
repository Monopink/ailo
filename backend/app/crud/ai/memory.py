"""
CRUD helpers for AI memories.

This module exposes strongly typed CRUD helpers for template memories and
instance memories so that services/admin APIs can reuse consistent DB access.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import asc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.ai.memory import AIInstanceMemory, AITemplateMemory
from app.schemas.ai.memory import (
    AIInstanceMemoryCreate,
    AIInstanceMemoryUpdate,
    AITemplateMemoryCreate,
    AITemplateMemoryUpdate,
)


class CRUDAITemplateMemory(
    CRUDBase[AITemplateMemory, AITemplateMemoryCreate, AITemplateMemoryUpdate]
):
    """CRUD helpers for template memories."""

    async def list_by_template(
        self, db: AsyncSession, *, template_id: int
    ) -> list[AITemplateMemory]:
        """Return all memories belonging to the specified template ordered by display_order."""

        stmt = (
            select(self.model)
            .where(self.model.template_id == template_id)
            .order_by(asc(self.model.display_order), asc(self.model.id))
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())


class CRUDAIInstanceMemory(
    CRUDBase[AIInstanceMemory, AIInstanceMemoryCreate, AIInstanceMemoryUpdate]
):
    """CRUD helpers for per-instance memories."""

    async def list_by_instance(
        self,
        db: AsyncSession,
        *,
        instance_id: int,
        include_archived: bool = False,
    ) -> list[AIInstanceMemory]:
        """Return memories for an instance, optionally filtering out archived rows."""

        stmt = select(self.model).where(self.model.instance_id == instance_id)
        if not include_archived:
            stmt = stmt.where(self.model.status == 1)
        stmt = stmt.order_by(
            asc(self.model.memory_type),
            asc(self.model.importance),
            asc(self.model.created_at),
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def list_recent_expiring(
        self, db: AsyncSession, *, limit: int = 100
    ) -> Sequence[AIInstanceMemory]:
        """Return recent memories that are close to expiration for monitoring/ops."""

        stmt = (
            select(self.model)
            .where(
                self.model.memory_type == "recent",
                self.model.status == 1,
                self.model.expires_at.is_not(None),
            )
            .order_by(asc(self.model.expires_at))
            .limit(limit)
        )
        result = await db.execute(stmt)
        return result.scalars().all()


ai_template_memory = CRUDAITemplateMemory(AITemplateMemory)
ai_instance_memory = CRUDAIInstanceMemory(AIInstanceMemory)

__all__ = [
    "CRUDAIInstanceMemory",
    "CRUDAITemplateMemory",
    "ai_instance_memory",
    "ai_template_memory",
]
