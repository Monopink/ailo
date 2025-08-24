"""
AI context CRUD operations.

This module contains CRUD operations for AI conversation contexts.
"""

from typing import List
from sqlalchemy import select, and_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from crud.base import CRUDBase
from models.ai import AIContext
from schemas.ai import AIContextCreate


class CRUDAIContext(CRUDBase[AIContext, AIContextCreate, dict]):
    """CRUD operations for AIContext model."""

    async def get_conversation_context(
        self, db: AsyncSession, *, character_qiao_id: str, user_qiao_id: str, limit: int = 20
    ) -> List[AIContext]:
        """Get conversation context between character and user."""
        result = await db.execute(
            select(self.model)
            .where(
                and_(
                    self.model.character_qiao_id == character_qiao_id,
                    self.model.user_qiao_id == user_qiao_id,
                )
            )
            .order_by(self.model.position)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_latest_context(
        self, db: AsyncSession, *, character_qiao_id: str, user_qiao_id: str, limit: int = 10
    ) -> List[AIContext]:
        """Get latest context messages."""
        result = await db.execute(
            select(self.model)
            .where(
                and_(
                    self.model.character_qiao_id == character_qiao_id,
                    self.model.user_qiao_id == user_qiao_id,
                )
            )
            .order_by(desc(self.model.position))
            .limit(limit)
        )
        return result.scalars().all()

    async def count_context_messages(
        self, db: AsyncSession, *, character_qiao_id: str, user_qiao_id: str
    ) -> int:
        """Count context messages."""
        result = await db.execute(
            select(func.count(self.model.id)).where(
                and_(
                    self.model.character_qiao_id == character_qiao_id,
                    self.model.user_qiao_id == user_qiao_id,
                )
            )
        )
        return result.scalar()

    async def cleanup_old_context(
        self, db: AsyncSession, *, character_qiao_id: str, user_qiao_id: str, keep_count: int = 50
    ) -> int:
        """Clean up old context messages, keeping only the latest ones."""
        # Get IDs of messages to keep
        keep_result = await db.execute(
            select(self.model.id)
            .where(
                and_(
                    self.model.character_qiao_id == character_qiao_id,
                    self.model.user_qiao_id == user_qiao_id,
                )
            )
            .order_by(desc(self.model.position))
            .limit(keep_count)
        )
        keep_ids = [row[0] for row in keep_result.all()]

        if not keep_ids:
            return 0

        # Delete messages not in keep list
        delete_result = await db.execute(
            select(self.model).where(
                and_(
                    self.model.character_qiao_id == character_qiao_id,
                    self.model.user_qiao_id == user_qiao_id,
                    ~self.model.id.in_(keep_ids),
                )
            )
        )
        messages_to_delete = delete_result.scalars().all()

        count = 0
        for message in messages_to_delete:
            await db.delete(message)
            count += 1

        await db.commit()
        return count


# Create instance
ai_context = CRUDAIContext(AIContext)
