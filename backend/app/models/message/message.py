"""
Message related models.

This module contains SQLAlchemy models for message history and delivery failures.
"""

from datetime import datetime
from typing import Any, Dict, Optional
from sqlalchemy import BigInteger, Integer, String, Text, DateTime, Index, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from enums import MessageDirection, MessageParticipantType, ServiceProvider, MessageType, MessageStatus
from models.base import Base, SnowflakeIDMixin, SnowflakeModel


class MessageHistory(Base, SnowflakeIDMixin):
    """
    Message history model.

    Complete message history and metadata.
    Message history is immutable - no updated_at field needed.
    """

    __tablename__ = "message_history"

    msg_id_server: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, comment="Server-generated message ID"
    )

    msg_id_provider: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, comment="Third-party service message ID"
    )

    msg_id_client: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, comment="Client-generated message ID"
    )

    conversation_id: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="Conversation identifier"
    )

    direction: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Message direction: 1=inbound, 2=outbound"
    )

    platform: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="Platform identifier")

    client_sent_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="Client-side sent time"
    )

    from_type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Sender type: 1=user, 2=ai_character"
    )

    from_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="Sender internal ID")

    from_qiao_id: Mapped[str] = mapped_column(String(32), nullable=False, comment="Sender external ID")

    to_type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Receiver type: 1=user, 2=ai_character"
    )

    to_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="Receiver internal ID")

    to_qiao_id: Mapped[str] = mapped_column(String(32), nullable=False, comment="Receiver external ID")

    message_type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Message type: 1=text, 2=image, 3=audio, 4=video, 5=file, 6=system"
    )

    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="Message content")

    service_provider: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Service provider: 1=leancloud, 2=internal"
    )

    status: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Message status: 1=sent, 2=delivered, 3=read, 4=failed"
    )

    message_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, nullable=True, comment="Message metadata (JSONB for better performance)"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now(), comment="Message creation timestamp"
    )

    # Indexes
    __table_args__ = (
        Index("idx_message_history_direction", "direction"),
        Index("idx_message_history_platform", "platform"),
        Index("idx_message_history_conversation_id", "conversation_id"),
        Index("idx_message_history_msg_id_server", "msg_id_server"),
        Index("idx_message_history_msg_id_client", "msg_id_client"),
        Index("idx_message_history_from_type", "from_type"),
        Index("idx_message_history_from_id", "from_id"),
        Index("idx_message_history_from_qiao_id", "from_qiao_id"),
        Index("idx_message_history_to_type", "to_type"),
        Index("idx_message_history_to_id", "to_id"),
        Index("idx_message_history_to_qiao_id", "to_qiao_id"),
        Index("idx_message_history_service_provider", "service_provider"),
        Index("idx_message_history_message_type", "message_type"),
        Index("idx_message_history_status", "status"),
        Index("idx_message_history_created_at", "created_at"),
        # PostgreSQL GIN index for JSONB field for better query performance
        Index("idx_message_history_metadata_gin", "message_metadata", postgresql_using="gin"),
    )


class MessageDeliveryFailure(SnowflakeModel):
    """
    Message delivery failure model.

    Failed message delivery tracking and retry management.
    """

    __tablename__ = "message_delivery_failures"

    msg_id_server: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="Original message ID, references message_history.msg_id_server"
    )

    from_type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Sender type: 1=user, 2=ai_character"
    )

    from_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="Sender internal ID")

    from_qiao_id: Mapped[str] = mapped_column(String(32), nullable=False, comment="Sender external ID")

    to_type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Receiver type: 1=user, 2=ai_character"
    )

    to_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="Receiver internal ID")

    to_qiao_id: Mapped[str] = mapped_column(String(32), nullable=False, comment="Receiver external ID")

    message_type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Message type: 1=text, 2=image, 3=audio, 4=video, 5=file, 6=system"
    )

    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="Message content")

    fail_reason_code: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="Failure reason code"
    )

    fail_detail: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Detailed error information"
    )

    retry_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Current retry count"
    )

    max_retry_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3, comment="Maximum retry count"
    )

    next_retry_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="Next retry time"
    )

    # Indexes
    __table_args__ = (
        Index("idx_message_delivery_failures_msg_id_server", "msg_id_server"),
        Index("idx_message_delivery_failures_from_qiao_id", "from_qiao_id"),
        Index("idx_message_delivery_failures_to_qiao_id", "to_qiao_id"),
        Index("idx_message_delivery_failures_retry_count", "retry_count"),
        Index("idx_message_delivery_failures_next_retry_at", "next_retry_at"),
    )
