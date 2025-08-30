"""
System statistics CRUD operations.

This module contains CRUD operations for various system statistics.
"""

from datetime import date, datetime, timedelta
from typing import List, Optional
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from crud.base import CRUDBase
from models.system import (
    StatsUserDaily,
    StatsUserWeekly,
    StatsUserMonthly,
    StatsRevenueDaily,
    StatsRevenueWeekly,
    StatsRevenueMonthly,
    StatsMessageDaily,
    StatsMessageWeekly,
    StatsMessageMonthly,
    StatsAIDaily,
    StatsAIWeekly,
    StatsAIMonthly,
)


class CRUDStatsUser(CRUDBase[StatsUserDaily, dict, dict]):
    """CRUD operations for user statistics."""

    async def get_by_date(self, db: AsyncSession, *, stat_date: date) -> Optional[StatsUserDaily]:
        """Get user stats by date."""
        result = await db.execute(select(self.model).where(self.model.stat_date == stat_date))
        return result.scalar_one_or_none()

    async def get_date_range(
        self, db: AsyncSession, *, start_date: date, end_date: date
    ) -> List[StatsUserDaily]:
        """Get user stats for date range."""
        result = await db.execute(
            select(self.model)
            .where(and_(self.model.stat_date >= start_date, self.model.stat_date <= end_date))
            .order_by(desc(self.model.stat_date))
        )
        return list(result.scalars().all())

    async def get_latest(self, db: AsyncSession, *, limit: int = 30) -> List[StatsUserDaily]:
        """Get latest user statistics."""
        result = await db.execute(select(self.model).order_by(desc(self.model.stat_date)).limit(limit))
        return list(result.scalars().all())


class CRUDStatsRevenue(CRUDBase[StatsRevenueDaily, dict, dict]):
    """CRUD operations for revenue statistics."""

    async def get_by_date(self, db: AsyncSession, *, stat_date: date) -> Optional[StatsRevenueDaily]:
        """Get revenue stats by date."""
        result = await db.execute(select(self.model).where(self.model.stat_date == stat_date))
        return result.scalar_one_or_none()

    async def get_date_range(
        self, db: AsyncSession, *, start_date: date, end_date: date
    ) -> List[StatsRevenueDaily]:
        """Get revenue stats for date range."""
        result = await db.execute(
            select(self.model)
            .where(and_(self.model.stat_date >= start_date, self.model.stat_date <= end_date))
            .order_by(desc(self.model.stat_date))
        )
        return list(result.scalars().all())

    async def get_latest(self, db: AsyncSession, *, limit: int = 30) -> List[StatsRevenueDaily]:
        """Get latest revenue statistics."""
        result = await db.execute(select(self.model).order_by(desc(self.model.stat_date)).limit(limit))
        return list(result.scalars().all())


class CRUDStatsMessage(CRUDBase[StatsMessageDaily, dict, dict]):
    """CRUD operations for message statistics."""

    async def get_by_date(self, db: AsyncSession, *, stat_date: date) -> Optional[StatsMessageDaily]:
        """Get message stats by date."""
        result = await db.execute(select(self.model).where(self.model.stat_date == stat_date))
        return result.scalar_one_or_none()

    async def get_date_range(
        self, db: AsyncSession, *, start_date: date, end_date: date
    ) -> List[StatsMessageDaily]:
        """Get message stats for date range."""
        result = await db.execute(
            select(self.model)
            .where(and_(self.model.stat_date >= start_date, self.model.stat_date <= end_date))
            .order_by(desc(self.model.stat_date))
        )
        return list(result.scalars().all())

    async def get_latest(self, db: AsyncSession, *, limit: int = 30) -> List[StatsMessageDaily]:
        """Get latest message statistics."""
        result = await db.execute(select(self.model).order_by(desc(self.model.stat_date)).limit(limit))
        return list(result.scalars().all())


class CRUDStatsAI(CRUDBase[StatsAIDaily, dict, dict]):
    """CRUD operations for AI statistics."""

    async def get_by_date(self, db: AsyncSession, *, stat_date: date) -> Optional[StatsAIDaily]:
        """Get AI stats by date."""
        result = await db.execute(select(self.model).where(self.model.stat_date == stat_date))
        return result.scalar_one_or_none()

    async def get_date_range(
        self, db: AsyncSession, *, start_date: date, end_date: date
    ) -> List[StatsAIDaily]:
        """Get AI stats for date range."""
        result = await db.execute(
            select(self.model)
            .where(and_(self.model.stat_date >= start_date, self.model.stat_date <= end_date))
            .order_by(desc(self.model.stat_date))
        )
        return list(result.scalars().all())

    async def get_latest(self, db: AsyncSession, *, limit: int = 30) -> List[StatsAIDaily]:
        """Get latest AI statistics."""
        result = await db.execute(select(self.model).order_by(desc(self.model.stat_date)).limit(limit))
        return list(result.scalars().all())


# Create instances
stats_user_daily = CRUDStatsUser(StatsUserDaily)
stats_revenue_daily = CRUDStatsRevenue(StatsRevenueDaily)
stats_message_daily = CRUDStatsMessage(StatsMessageDaily)
stats_ai_daily = CRUDStatsAI(StatsAIDaily)
