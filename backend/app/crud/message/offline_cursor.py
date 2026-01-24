"""Offline message cursor CRUD operations."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.message.offline_cursor import MessageOfflineCursor
from app.schemas.message.offline import OfflineCursorCreate, OfflineCursorUpdate


class CRUDMessageOfflineCursor(
    CRUDBase[MessageOfflineCursor, OfflineCursorCreate, OfflineCursorUpdate]
):
    """CRUD operations for MessageOfflineCursor model."""

    async def get_by_user_and_device(
        self, db: AsyncSession, *, user_id: int, device_id: str
    ) -> MessageOfflineCursor | None:
        """Get cursor for specific user and device."""
        result = await db.execute(
            select(self.model).where(
                self.model.user_id == user_id,
                self.model.device_id == device_id,
            )
        )
        return result.scalar_one_or_none()

    async def touch_last_pull(
        self, db: AsyncSession, *, cursor: MessageOfflineCursor
    ) -> MessageOfflineCursor:
        """Update last_pull_at timestamp."""
        cursor.last_pull_at = datetime.now(UTC)
        db.add(cursor)
        await db.commit()
        await db.refresh(cursor)
        return cursor


offline_cursor = CRUDMessageOfflineCursor(MessageOfflineCursor)
