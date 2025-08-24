"""
Message delivery failure CRUD operations.

This module contains CRUD operations for message delivery failures and retry logic.
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from crud.base import CRUDBase
from models.message import MessageDeliveryFailure


class CRUDMessageFailure(CRUDBase[MessageDeliveryFailure, dict, dict]):
    """CRUD operations for MessageDeliveryFailure model."""

    async def get_by_message_id(
        self, db: AsyncSession, *, msg_id_server: str
    ) -> Optional[MessageDeliveryFailure]:
        """Get failure record by message ID."""
        result = await db.execute(select(self.model).where(self.model.msg_id_server == msg_id_server))
        return result.scalar_one_or_none()

    async def get_retry_pending(
        self, db: AsyncSession, *, limit: int = 100
    ) -> List[MessageDeliveryFailure]:
        """Get messages pending retry."""
        now = datetime.utcnow()
        result = await db.execute(
            select(self.model)
            .where(
                and_(self.model.retry_count < self.model.max_retry_count, self.model.next_retry_at <= now)
            )
            .limit(limit)
        )
        return result.scalars().all()

    async def increment_retry_count(
        self, db: AsyncSession, *, msg_id_server: str, next_retry_at: datetime
    ) -> Optional[MessageDeliveryFailure]:
        """Increment retry count and update next retry time."""
        failure = await self.get_by_message_id(db, msg_id_server=msg_id_server)
        if failure:
            failure.retry_count += 1
            failure.next_retry_at = next_retry_at
            db.add(failure)
            await db.commit()
            await db.refresh(failure)
        return failure


# Create instance
message_failure = CRUDMessageFailure(MessageDeliveryFailure)
