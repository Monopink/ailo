"""Message related models.

This module contains SQLAlchemy models for message history (message facts).
Delivery status is intentionally stored outside message_history.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm import relationship as orm_relationship

from app.models.base import ImmutableSnowflakeModel
from app.type_defs import JSONDict

if TYPE_CHECKING:
    from app.models.ai.log import AIRequestLog


class MessageHistory(ImmutableSnowflakeModel):
    """Message history model.

    Complete message history and metadata.
    Message history is append-only; delivery state is tracked in message_deliveries and ACK cursors.
    """

    __tablename__ = "message_history"

    direction: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Message direction: 1=inbound, 2=outbound"
    )

    conversation_id: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="Conversation ID, references contacts.conversation_id"
    )

    msg_id_server: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, comment="Server-generated timeline message ID"
    )

    msg_id_provider_inbound: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="Inbound provider message ID"
    )

    msg_id_client: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="Client-generated message ID"
    )

    client_sent_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
        comment="Client-side sent time (public API field: client_sent_time_ms)",
    )

    sent_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
        comment="Server-recognized event time (public API field: sent_time_ms)",
    )

    from_type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Sender type: 1=user, 2=ai, 3=admin, 4=system"
    )

    from_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="Sender internal ID")

    from_qiao_id: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="Sender external ID"
    )

    to_type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Receiver type: 1=user, 2=ai, 3=admin, 4=system"
    )

    to_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="Receiver internal ID")

    to_qiao_id: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="Receiver external ID"
    )

    message_type: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Message type (see docs/spec/message/schema.md)",
    )

    content: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Message content")

    inbound_provider: Mapped[int | None] = mapped_column(
        SmallInteger,
        nullable=True,
        comment="Inbound provider enum (see app.enums.MessageTransportProvider)",
    )

    inbound_device_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        comment="Inbound device_id (websocket inbound only)",
    )

    message_metadata: Mapped[JSONDict | None] = mapped_column(
        JSONB, nullable=True, comment="Message metadata (JSONB for better performance)"
    )

    llm_request_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment="ai_request_logs.id (llm_request_id); only set for assistant outbound messages",
    )
    llm_request_log: Mapped["AIRequestLog | None"] = orm_relationship(
        "AIRequestLog",
        primaryjoin="MessageHistory.llm_request_id == AIRequestLog.id",
        foreign_keys="[MessageHistory.llm_request_id]",
        lazy="select",
        viewonly=True,
        uselist=False,
    )

    # Timestamps (created_at inherited from ImmutableSnowflakeModel)

    # Indexes - Only essential indexes for MVP
    # Note: msg_id_server already has unique index
    __table_args__ = (
        CheckConstraint(
            "inbound_provider IS NULL OR inbound_provider IN (1, 2)",
            name="ck_message_history_inbound_provider",
        ),
        UniqueConstraint(
            "conversation_id", "msg_id_client", name="uq_message_history_conv_client_id"
        ),
        Index("idx_message_history_from_qiao_id", "from_qiao_id"),
        Index("idx_message_history_to_qiao_id", "to_qiao_id"),
        Index("idx_message_history_conversation_id", "conversation_id"),
        Index("idx_message_history_created_at", "created_at"),
        Index("idx_message_history_msg_id_client", "msg_id_client"),
        Index("idx_message_history_llm_request_id", "llm_request_id"),
        # PostgreSQL GIN index for JSONB field for better query performance
        Index("idx_message_history_metadata_gin", "message_metadata", postgresql_using="gin"),
    )
