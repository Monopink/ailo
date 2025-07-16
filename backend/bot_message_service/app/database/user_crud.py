"""
CRUD operations for User entities.
"""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from .base_crud import CRUDBase
from ..models.user import User


class CRUDUser(CRUDBase[User]):
    """CRUD operations for User entities."""

    async def get_by_entity_id(self, db: AsyncSession, entity_id: str) -> Optional[User]:
        """Get user by entity_id."""
        result = await db.execute(select(User).where(User.entity_id == entity_id))
        return result.scalar_one_or_none()


# Create instance
user_crud = CRUDUser(User)
