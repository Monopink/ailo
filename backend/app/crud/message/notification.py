"""Notification push history CRUD operations."""

from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.enums import MessageDeliveryStatus, NotificationStatus
from app.models.message import MessageDelivery
from app.models.message.notification import NotificationPushHistory

_NOTIFICATION_PENDING_TIMEOUT_SECONDS = 60


class CRUDNotificationPushHistory(CRUDBase[NotificationPushHistory, BaseModel, BaseModel]):
    """CRUD operations for NotificationPushHistory model."""

    async def create_notification(
        self,
        db: AsyncSession,
        *,
        to_qiao_id: str,
        notification_type: int,
        action_data: dict[str, Any],
        msg_id_server: str,
        planned_endpoint_count: int,
    ) -> NotificationPushHistory:
        """Create notification record.

        Args:
            db: Database session
            to_qiao_id: Receiver's qiao_id
            notification_type: Notification type (1=CONTACT_REQUEST)
            action_data: Notification action and data (JSONB)
            msg_id_server: Notification transport message ID
            planned_endpoint_count: Planned websocket endpoint delivery count

        Returns:
            Created notification record

        """
        notification = NotificationPushHistory(
            to_qiao_id=to_qiao_id,
            notification_type=notification_type,
            action_data=action_data,
            msg_id_server=msg_id_server,
            status=NotificationStatus.PENDING,
            planned_endpoint_count=max(0, planned_endpoint_count),
            completed_endpoint_count=0,
            succeeded_endpoint_count=0,
        )
        db.add(notification)
        await db.commit()
        await db.refresh(notification)
        return notification

    async def mark_as_sent(
        self,
        db: AsyncSession,
        *,
        notification_id: int,
    ) -> NotificationPushHistory | None:
        """Mark notification as sent."""
        notification = await self.get(db, record_id=notification_id)
        if notification:
            notification.status = NotificationStatus.SENT
            notification.error_message = None
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
    ) -> NotificationPushHistory | None:
        """Mark notification as failed.

        Args:
            db: Database session
            notification_id: Notification ID
            error_message: Error message

        Returns:
            Updated notification record or None if not found

        """
        notification = await self.get(db, record_id=notification_id)
        if notification:
            notification.status = NotificationStatus.FAILED
            notification.error_message = error_message
            db.add(notification)
            await db.commit()
            await db.refresh(notification)
        return notification

    async def refresh_delivery_progress(
        self,
        db: AsyncSession,
        *,
        notification_id: int,
        msg_id_server: str,
    ) -> NotificationPushHistory | None:
        """Refresh notification delivery counters and finalize status if needed."""
        notification = await self.get(db, record_id=notification_id)
        if notification is None:
            return None

        completed_result = await db.execute(
            select(func.count(MessageDelivery.id)).where(
                MessageDelivery.msg_id_server == msg_id_server,
                MessageDelivery.status.in_(
                    [MessageDeliveryStatus.DISPATCHED, MessageDeliveryStatus.FAILED]
                ),
            )
        )
        completed_count = int(completed_result.scalar_one() or 0)

        succeeded_result = await db.execute(
            select(func.count(MessageDelivery.id)).where(
                MessageDelivery.msg_id_server == msg_id_server,
                MessageDelivery.status == MessageDeliveryStatus.DISPATCHED,
            )
        )
        succeeded_count = int(succeeded_result.scalar_one() or 0)

        notification.completed_endpoint_count = completed_count
        notification.succeeded_endpoint_count = succeeded_count
        planned_count = max(0, int(notification.planned_endpoint_count))

        if planned_count > 0 and completed_count >= planned_count:
            if succeeded_count > 0:
                notification.status = NotificationStatus.SENT
                notification.error_message = None
            else:
                notification.status = NotificationStatus.FAILED
                notification.error_message = "No active websocket endpoint delivery succeeded"
        elif planned_count == 0:
            notification.status = NotificationStatus.FAILED
            notification.error_message = "No active websocket endpoint"
        else:
            notification.status = NotificationStatus.PENDING
            notification.error_message = None

        db.add(notification)
        await db.commit()
        await db.refresh(notification)
        return notification

    async def mark_stale_pending_as_failed(
        self,
        db: AsyncSession,
        *,
        now: datetime | None = None,
    ) -> int:
        """Mark stale pending notifications as failed."""
        effective_now = now or datetime.now(UTC)
        stale_before = effective_now - timedelta(seconds=_NOTIFICATION_PENDING_TIMEOUT_SECONDS)
        result = await db.execute(
            select(NotificationPushHistory).where(
                NotificationPushHistory.status == NotificationStatus.PENDING,
                NotificationPushHistory.created_at <= stale_before,
            )
        )
        stale_notifications = list(result.scalars().all())
        if not stale_notifications:
            return 0

        for notification in stale_notifications:
            notification.status = NotificationStatus.FAILED
            notification.error_message = "Notification delivery timeout"
            db.add(notification)

        await db.commit()
        return len(stale_notifications)

    async def get_user_notifications(
        self,
        db: AsyncSession,
        *,
        to_qiao_id: str,
        notification_type: int | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[NotificationPushHistory]:
        """Get user's notifications.

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
