"""
Notification push history model.

This module contains SQLAlchemy model for notification push history.
"""

from datetime import datetime
from typing import Any

from enums import NotificationStatus
from models.base import SnowflakeModel
from sqlalchemy import Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column


class NotificationPushHistory(SnowflakeModel):
    """
    Notification push history model.

    Tracks all notification messages sent to users.
    Used for debugging, analytics, and potential retry logic.
    """

    __tablename__ = "notification_push_history"

    to_qiao_id: Mapped[str] = mapped_column(String(32), nullable=False, comment="Receiver qiao_id")

    notification_type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Notification type: 1=contact_request"
    )

    action_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, comment="Action and data objects (JSON)"
    )

    status: Mapped[int] = mapped_column(
        Integer, nullable=False, default=NotificationStatus.SENT, comment="Status: 1=sent, 2=failed"
    )

    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Error message if failed"
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="NOW()", comment="Creation time"
    )

    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default="NOW()",
        onupdate=datetime.now,
        comment="Last update time",
    )

    __table_args__ = (Index("idx_notification_push_created_at", "created_at"),)
