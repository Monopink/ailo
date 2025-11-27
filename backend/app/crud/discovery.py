"""
Discovery (Square) CRUD helpers.
"""

from __future__ import annotations

from typing import List

from crud.base import CRUDBase
from models.discovery import SquareTypeEntry
from schemas.discovery import SquareEntryCreate, SquareEntryUpdate
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class CRUDSquareEntry(CRUDBase[SquareTypeEntry, SquareEntryCreate, SquareEntryUpdate]):
    async def get_active_by_category(
        self, db: AsyncSession, *, category: str, limit: int
    ) -> List[SquareTypeEntry]:
        stmt = (
            select(self.model)
            .where(self.model.square_category == category, self.model.status == 1)
            .order_by(self.model.id.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())


square_entry = CRUDSquareEntry(SquareTypeEntry)
