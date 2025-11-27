"""
Notification push history CRUD operations.
"""

from typing import List, Optional

from crud.base import CRUDBase
from enums.common import NotificationStatus
from models.message.notification import NotificationPushHistory
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession


class CRUDNotificationPushHistory(CRUDBase[NotificationPushHistory, BaseModel, BaseModel]):
    """CRUD operations for NotificationPushHistory model."""

    async def create_notification(
        self,
        db: AsyncSession,
        *,
        to_qiao_id: str,
        notification_type: int,
        action_data: dict,
    ) -> NotificationPushHistory:
        """
        Create notification record.

        Args:
            db: Database session
            to_qiao_id: Receiver's qiao_id
            notification_type: Notification type (1=CONTACT_REQUEST)
            action_data: Notification action and data (JSONB)

        Returns:
            Created notification record
        """
        notification = NotificationPushHistory(
            to_qiao_id=to_qiao_id,
            notification_type=notification_type,
            action_data=action_data,
            status=NotificationStatus.SENT,
        )
        db.add(notification)
        await db.commit()
        await db.refresh(notification)
        return notification

    async def mark_as_failed(
        self,
        db: AsyncSession,
        *,
        notification_id: int,
        error_message: str,
    ) -> Optional[NotificationPushHistory]:
        """
        Mark notification as failed.

        Args:
            db: Database session
            notification_id: Notification ID
            error_message: Error message

        Returns:
            Updated notification record or None if not found
        """
        notification = await self.get(db, id=notification_id)
        if notification:
            notification.status = NotificationStatus.FAILED
            notification.error_message = error_message
            db.add(notification)
            await db.commit()
            await db.refresh(notification)
        return notification

    async def get_user_notifications(
        self,
        db: AsyncSession,
        *,
        to_qiao_id: str,
        notification_type: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[NotificationPushHistory]:
        """
        Get user's notifications.

        Args:
            db: Database session
            to_qiao_id: User's qiao_id
            notification_type: Filter by notification type (optional)
            skip: Pagination offset
            limit: Maximum number of results

        Returns:
            List of notification records
        """
        conditions = [self.model.to_qiao_id == to_qiao_id]
        if notification_type:
            conditions.append(self.model.notification_type == notification_type)

        result = await db.execute(
            select(self.model)
            .where(and_(*conditions))
            .order_by(self.model.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())


# Create instance
notification_push_history = CRUDNotificationPushHistory(NotificationPushHistory)
