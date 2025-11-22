"""
Message related models.

This module contains SQLAlchemy models for message history and delivery failures.
"""

from datetime import datetime
from typing import Any, Dict, Optional
from sqlalchemy import BigInteger, Integer, String, Text, DateTime, Index, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from enums import MessageDirection, MessageParticipantType, ServiceProvider, MessageType, MessageStatus
from models.base import ImmutableSnowflakeModel, SnowflakeModel


class MessageHistory(ImmutableSnowflakeModel):
    """
    Message history model.

    Complete message history and metadata.
    Message history is immutable - no updated_at field needed.
    """

    __tablename__ = "message_history"

    msg_id_server: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, comment="Server-generated message ID"
    )

    msg_id_provider_inbound: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, comment="Inbound provider message ID"
    )

    msg_id_provider_outbound: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, comment="Outbound provider message ID"
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
        TIMESTAMP(timezone=True), nullable=True, comment="Client-side sent time"
    )

    sent_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, comment="Original message sent time"
    )

    from_type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Sender type: 1=user, 2=ai_instance"
    )

    from_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="Sender internal ID")

    from_qiao_id: Mapped[str] = mapped_column(String(32), nullable=False, comment="Sender external ID")

    to_type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Receiver type: 1=user, 2=ai_instance"
    )

    to_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="Receiver internal ID")

    to_qiao_id: Mapped[str] = mapped_column(String(32), nullable=False, comment="Receiver external ID")

    message_type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Message type: 1=text, 2=image, 3=audio, 4=video, 5=file, 6=system"
    )

    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="Message content")

    service_provider: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Service provider: 1=internal, 2=leancloud"
    )

    status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
        comment="Message status: 1=sent, 2=delivered, 3=read, 4=failed",
    )

    message_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, nullable=True, comment="Message metadata (JSONB for better performance)"
    )

    # Timestamps (created_at inherited from ImmutableSnowflakeModel)

    # Indexes - Only essential indexes for MVP
    # Note: msg_id_server already has unique index
    __table_args__ = (
        UniqueConstraint("conversation_id", "msg_id_client", name="uq_message_history_conv_client_id"),
        Index("idx_message_history_from_qiao_id", "from_qiao_id"),
        Index("idx_message_history_to_qiao_id", "to_qiao_id"),
        Index("idx_message_history_conversation_id", "conversation_id"),
        Index("idx_message_history_created_at", "created_at"),
        Index("idx_message_history_msg_id_client", "msg_id_client"),
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
        Integer, nullable=False, comment="Sender type: 1=user, 2=ai_instance"
    )

    from_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="Sender internal ID")

    from_qiao_id: Mapped[str] = mapped_column(String(32), nullable=False, comment="Sender external ID")

    to_type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Receiver type: 1=user, 2=ai_instance"
    )

    to_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="Receiver internal ID")

    to_qiao_id: Mapped[str] = mapped_column(String(32), nullable=False, comment="Receiver external ID")

    message_type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Message type: 1=text, 2=image, 3=audio, 4=video, 5=file, 6=system"
    )

    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="Message content")

    service_provider: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Service provider: 1=internal, 2=leancloud"
    )

    fail_reason_code: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="Failure reason code"
    )

    fail_detail: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Detailed error information"
    )

    retry_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0"), comment="Current retry count"
    )

    max_retry_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3, server_default=text("3"), comment="Maximum retry count"
    )

    next_retry_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, comment="Next retry time"
    )
