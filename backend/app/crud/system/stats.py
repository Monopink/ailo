"""
System statistics CRUD operations.

This module contains CRUD operations for various system statistics.
"""

from datetime import date

from pydantic import BaseModel
from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.system import (
    StatsAIDaily,
    StatsMessageDaily,
    StatsUserDaily,
)


class _StatsSchema(BaseModel):
    """
    Dummy schema for read-only stats CRUD operations.

    Stats tables are read-only (populated by background jobs),
    so create/update operations are not used.
    """


class CRUDStatsUser(CRUDBase[StatsUserDaily, _StatsSchema, _StatsSchema]):
    """CRUD operations for user statistics."""

    async def get_by_date(self, db: AsyncSession, *, stat_date: date) -> StatsUserDaily | None:
        """Get user stats by date."""
        result = await db.execute(select(self.model).where(self.model.stat_date == stat_date))
        return result.scalar_one_or_none()

    async def get_date_range(
        self, db: AsyncSession, *, start_date: date, end_date: date
    ) -> list[StatsUserDaily]:
        """Get user stats for date range."""
        result = await db.execute(
            select(self.model)
            .where(and_(self.model.stat_date >= start_date, self.model.stat_date <= end_date))
            .order_by(desc(self.model.stat_date))
        )
        return list(result.scalars().all())

    async def get_latest(self, db: AsyncSession, *, limit: int = 30) -> list[StatsUserDaily]:
        """Get latest user statistics."""
        result = await db.execute(
            select(self.model).order_by(desc(self.model.stat_date)).limit(limit)
        )
        return list(result.scalars().all())


class CRUDStatsMessage(CRUDBase[StatsMessageDaily, _StatsSchema, _StatsSchema]):
    """CRUD operations for message statistics."""

    async def get_by_date(self, db: AsyncSession, *, stat_date: date) -> StatsMessageDaily | None:
        """Get message stats by date."""
        result = await db.execute(select(self.model).where(self.model.stat_date == stat_date))
        return result.scalar_one_or_none()

    async def get_date_range(
        self, db: AsyncSession, *, start_date: date, end_date: date
    ) -> list[StatsMessageDaily]:
        """Get message stats for date range."""
        result = await db.execute(
            select(self.model)
            .where(and_(self.model.stat_date >= start_date, self.model.stat_date <= end_date))
            .order_by(desc(self.model.stat_date))
        )
        return list(result.scalars().all())

    async def get_latest(self, db: AsyncSession, *, limit: int = 30) -> list[StatsMessageDaily]:
        """Get latest message statistics."""
        result = await db.execute(
            select(self.model).order_by(desc(self.model.stat_date)).limit(limit)
        )
        return list(result.scalars().all())


class CRUDStatsAI(CRUDBase[StatsAIDaily, _StatsSchema, _StatsSchema]):
    """CRUD operations for AI statistics."""

    async def get_by_date(self, db: AsyncSession, *, stat_date: date) -> StatsAIDaily | None:
        """Get AI stats by date."""
        result = await db.execute(select(self.model).where(self.model.stat_date == stat_date))
        return result.scalar_one_or_none()

    async def get_date_range(
        self, db: AsyncSession, *, start_date: date, end_date: date
    ) -> list[StatsAIDaily]:
        """Get AI stats for date range."""
        result = await db.execute(
            select(self.model)
            .where(and_(self.model.stat_date >= start_date, self.model.stat_date <= end_date))
            .order_by(desc(self.model.stat_date))
        )
        return list(result.scalars().all())

    async def get_latest(self, db: AsyncSession, *, limit: int = 30) -> list[StatsAIDaily]:
        """Get latest AI statistics."""
        result = await db.execute(
            select(self.model).order_by(desc(self.model.stat_date)).limit(limit)
        )
        return list(result.scalars().all())


# Create instances
stats_user_daily = CRUDStatsUser(StatsUserDaily)
stats_message_daily = CRUDStatsMessage(StatsMessageDaily)
stats_ai_daily = CRUDStatsAI(StatsAIDaily)
