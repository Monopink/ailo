"""Discovery (Square) CRUD helpers."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.content import SquareTypeEntry
from app.schemas.discovery import SquareEntryCreate, SquareEntryUpdate


class CRUDSquareEntry(CRUDBase[SquareTypeEntry, SquareEntryCreate, SquareEntryUpdate]):
    """CRUD helpers for Square entries."""

    async def get_active_by_category(
        self, db: AsyncSession, *, category_key: str, limit: int
    ) -> list[SquareTypeEntry]:
        """Return active square entries for the given category."""
        stmt = (
            select(self.model)
            .where(self.model.category_key == category_key, self.model.status == 1)
            .order_by(self.model.id.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())


square_entry = CRUDSquareEntry(SquareTypeEntry)
