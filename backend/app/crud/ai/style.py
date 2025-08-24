"""
AI style CRUD operations.

This module contains CRUD operations for AI styles.
"""

from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from crud.base import CRUDBase
from models.ai import AIStyle
from schemas.ai import AIStyleCreate


class CRUDAIStyle(CRUDBase[AIStyle, AIStyleCreate, dict]):
    """CRUD operations for AIStyle model."""

    async def get_active_styles(self, db: AsyncSession) -> List[AIStyle]:
        """Get all active AI styles."""
        result = await db.execute(
            select(self.model).where(self.model.status == 1).order_by(self.model.created_at)
        )
        return result.scalars().all()


# Create instance
ai_style = CRUDAIStyle(AIStyle)
