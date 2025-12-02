"""
CRUD operations for LLM test logs.

This module provides database operations for LLM configuration test logs.
"""

from crud.base import ImmutableCRUDBase
from models.llm import LLMTestLog
from schemas.llm import LLMTestLogCreate
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession


class CRUDLLMTestLog(ImmutableCRUDBase[LLMTestLog, LLMTestLogCreate]):
    """CRUD operations for LLM test logs (immutable)."""

    async def get_by_config_id(
        self, db: AsyncSession, config_id: int, limit: int = 100
    ) -> list[LLMTestLog]:
        """
        Get test logs by configuration ID.

        Args:
            db: Database session
            config_id: Configuration ID
            limit: Maximum number of logs to return

        Returns:
            List of test logs ordered by creation time (newest first)
        """
        result = await db.execute(
            select(LLMTestLog)
            .where(LLMTestLog.config_id == config_id)
            .order_by(desc(LLMTestLog.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_recent_logs(self, db: AsyncSession, limit: int = 50) -> list[LLMTestLog]:
        """
        Get recent test logs across all configurations.

        Args:
            db: Database session
            limit: Maximum number of logs to return

        Returns:
            List of test logs ordered by creation time (newest first)
        """
        result = await db.execute(
            select(LLMTestLog).order_by(desc(LLMTestLog.created_at)).limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_status(
        self, db: AsyncSession, status: int, limit: int = 100
    ) -> list[LLMTestLog]:
        """
        Get test logs by status.

        Args:
            db: Database session
            status: Status code (1=success, 2=failed, 3=timeout)
            limit: Maximum number of logs to return

        Returns:
            List of test logs with specified status
        """
        result = await db.execute(
            select(LLMTestLog)
            .where(LLMTestLog.status == status)
            .order_by(desc(LLMTestLog.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())


# Create instance
llm_test_log = CRUDLLMTestLog(LLMTestLog)
