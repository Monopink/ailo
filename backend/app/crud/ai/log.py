"""
AI request log CRUD operations.

This module contains CRUD operations for AI request logs and statistics.
"""

from typing import List
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from crud.base import CRUDBase
from models.ai import AIRequestLog
from schemas.ai import AIRequestLogCreate
from enums import AIRequestStatus


class CRUDAIRequestLog(CRUDBase[AIRequestLog, AIRequestLogCreate, dict]):
    """CRUD operations for AIRequestLog model."""

    async def get_character_logs(
        self, db: AsyncSession, *, character_id: int, skip: int = 0, limit: int = 100
    ) -> List[AIRequestLog]:
        """Get request logs for a character."""
        result = await db.execute(
            select(self.model)
            .where(self.model.character_id == character_id)
            .order_by(desc(self.model.created_at))
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_user_logs(
        self, db: AsyncSession, *, user_id: int, skip: int = 0, limit: int = 100
    ) -> List[AIRequestLog]:
        """Get request logs for a user."""
        result = await db.execute(
            select(self.model)
            .where(self.model.user_id == user_id)
            .order_by(desc(self.model.created_at))
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_failed_requests(self, db: AsyncSession, *, limit: int = 100) -> List[AIRequestLog]:
        """Get failed AI requests."""
        result = await db.execute(
            select(self.model)
            .where(self.model.status == AIRequestStatus.FAILED)
            .order_by(desc(self.model.created_at))
            .limit(limit)
        )
        return result.scalars().all()

    async def get_stats_by_character(self, db: AsyncSession, *, character_id: int) -> dict:
        """Get statistics for a character."""
        result = await db.execute(
            select(
                func.count(self.model.id).label("total_requests"),
                func.sum(self.model.token_count).label("total_tokens"),
                func.avg(self.model.response_time).label("avg_response_time"),
            ).where(self.model.character_id == character_id)
        )
        row = result.first()
        return {
            "total_requests": row.total_requests or 0,
            "total_tokens": row.total_tokens or 0,
            "avg_response_time": row.avg_response_time or 0,
        }


# Create instance
ai_request_log = CRUDAIRequestLog(AIRequestLog)
