"""Notification push history model.

This module contains SQLAlchemy model for notification push history.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm import relationship as orm_relationship

from app.enums import NotificationStatus
from app.models.base import SnowflakeModel
from app.type_defs import JSONDict

if TYPE_CHECKING:
    from app.models.user import User


class NotificationPushHistory(SnowflakeModel):
    """Notification push history model.

    Tracks all notification messages sent to users.
    Used for debugging, analytics, and potential retry logic.
    """

    __tablename__ = "notification_push_history"

    to_qiao_id: Mapped[str] = mapped_column(String(32), nullable=False, comment="Receiver qiao_id")

    notification_type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Notification type: 1=contact_request"
    )

    action_data: Mapped[JSONDict] = mapped_column(
        JSONB, nullable=False, comment="Action and data objects (JSON)"
    )

    msg_id_server: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="Notification transport message ID"
    )

    status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=NotificationStatus.PENDING,
        comment="Status: 0=pending, 1=sent, 2=failed",
    )

    planned_endpoint_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Planned websocket endpoint delivery count"
    )

    completed_endpoint_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Completed websocket endpoint delivery count"
    )

    succeeded_endpoint_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Succeeded websocket endpoint delivery count"
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

    user: Mapped["User | None"] = orm_relationship(
        "User",
        primaryjoin="NotificationPushHistory.to_qiao_id == User.qiao_id",
        foreign_keys="[NotificationPushHistory.to_qiao_id]",
        lazy="select",
        viewonly=True,
        uselist=False,
    )

    __table_args__ = (
        Index("idx_notification_push_created_at", "created_at"),
        Index("idx_notification_push_msg_id_server", "msg_id_server"),
    )
