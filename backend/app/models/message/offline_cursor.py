"""Offline message cursor model."""

from datetime import datetime

from sqlalchemy import BigInteger, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import SnowflakeModel


class MessageOfflineCursor(SnowflakeModel):
    """Offline message cursor for per-device delivery tracking."""

    __tablename__ = "message_offline_cursor"

    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="User internal ID")
    user_qiao_id: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="User external ID"
    )
    device_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="Device/installation UUID"
    )
    last_ack_msg_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="Latest acknowledged server message ID",
    )
    last_ack_sent_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
        comment="Latest acknowledged message sent time",
    )
    last_pull_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
        comment="Latest offline pull timestamp",
    )

    __table_args__ = (
        UniqueConstraint("user_id", "device_id", name="uq_message_offline_cursor_user_device"),
        Index("idx_message_offline_cursor_user_qiao_id", "user_qiao_id"),
        Index("idx_message_offline_cursor_device_id", "device_id"),
        Index("idx_message_offline_cursor_last_ack_sent_at", "last_ack_sent_at"),
    )
