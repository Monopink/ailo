"""
Emoticon CRUD operations.

This module contains CRUD operations for emoticon management.
"""

from typing import List, Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from crud.base import CRUDBase
from models.message import Emoticon
from schemas.message import EmoticonCreate
from enums import EmoticonCategory


class CRUDEmoticon(CRUDBase[Emoticon, EmoticonCreate, dict]):
    """CRUD operations for Emoticon model."""

    async def get_by_code(self, db: AsyncSession, *, code: str) -> Optional[Emoticon]:
        """Get emoticon by code."""
        result = await db.execute(select(self.model).where(self.model.code == code))
        return result.scalar_one_or_none()

    async def get_by_category(
        self, db: AsyncSession, *, category: EmoticonCategory, skip: int = 0, limit: int = 100
    ) -> List[Emoticon]:
        """Get emoticons by category."""
        result = await db.execute(
            select(self.model)
            .where(and_(self.model.category == category, self.model.status == 1))  # Active
            .order_by(self.model.sort_order, self.model.created_at)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_all_active(self, db: AsyncSession) -> List[Emoticon]:
        """Get all active emoticons."""
        result = await db.execute(
            select(self.model)
            .where(self.model.status == 1)
            .order_by(self.model.category, self.model.sort_order)
        )
        return list(result.scalars().all())


# Create instance
emoticon = CRUDEmoticon(Emoticon)
