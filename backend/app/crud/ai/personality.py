"""
AI personality CRUD operations.

This module contains CRUD operations for AI personalities.
"""

from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from crud.base import CRUDBase
from models.ai import AIPersonality
from schemas.ai import AIPersonalityCreate


class CRUDAIPersonality(CRUDBase[AIPersonality, AIPersonalityCreate, dict]):
    """CRUD operations for AIPersonality model."""

    async def get_active_personalities(self, db: AsyncSession) -> List[AIPersonality]:
        """Get all active AI personalities."""
        result = await db.execute(
            select(self.model).where(self.model.status == 1).order_by(self.model.created_at)
        )
        return result.scalars().all()


# Create instance
ai_personality = CRUDAIPersonality(AIPersonality)
