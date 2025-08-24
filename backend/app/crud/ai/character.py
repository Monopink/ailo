"""
AI character CRUD operations.

This module contains CRUD operations for AI characters.
"""

from typing import List, Optional
from sqlalchemy import select, and_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from crud.base import CRUDBaseWithQiaoId
from models.ai import AICharacter
from schemas.ai import AICharacterCreate, AICharacterUpdate
from enums import AICharacterCreator


class CRUDAICharacter(CRUDBaseWithQiaoId[AICharacter, AICharacterCreate, AICharacterUpdate]):
    """CRUD operations for AICharacter model."""

    async def get_by_user(
        self, db: AsyncSession, *, user_qiao_id: str, skip: int = 0, limit: int = 100
    ) -> List[AICharacter]:
        """Get AI characters created by user."""
        result = await db.execute(
            select(self.model)
            .where(self.model.user_qiao_id == user_qiao_id)
            .order_by(desc(self.model.created_at))
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_by_category(
        self, db: AsyncSession, *, category: str, skip: int = 0, limit: int = 100
    ) -> List[AICharacter]:
        """Get AI characters by category."""
        result = await db.execute(
            select(self.model)
            .where(self.model.category == category)
            .order_by(desc(self.model.created_at))
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_system_characters(
        self, db: AsyncSession, *, skip: int = 0, limit: int = 100
    ) -> List[AICharacter]:
        """Get system-created AI characters."""
        result = await db.execute(
            select(self.model)
            .where(self.model.created_by == AICharacterCreator.SYSTEM)
            .order_by(desc(self.model.created_at))
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def count_user_characters(self, db: AsyncSession, *, user_qiao_id: str) -> int:
        """Count user's AI characters."""
        result = await db.execute(
            select(func.count(self.model.id)).where(self.model.user_qiao_id == user_qiao_id)
        )
        return result.scalar()

    async def search_characters(
        self, db: AsyncSession, *, query: str, category: Optional[str] = None, limit: int = 20
    ) -> List[AICharacter]:
        """Search AI characters."""
        conditions = [self.model.qiao_id.ilike(f"%{query}%")]
        if category:
            conditions.append(self.model.category == category)

        result = await db.execute(select(self.model).where(and_(*conditions)).limit(limit))
        return result.scalars().all()


# Create instance
ai_character = CRUDAICharacter(AICharacter)
