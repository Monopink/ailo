"""Message routing models.

These tables support provider-agnostic message delivery:
- message_devices: per (user_id, device_id) offline cursor and activity
- message_endpoints: active deliverable endpoint binding (provider + lease)
- message_deliveries: per-endpoint delivery record
- message_dispatch_outbox: dispatch task queue with retry scheduling state
"""

from __future__ import annotations

from datetime import datetime
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
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import SnowflakeModel


class MessageDevice(SnowflakeModel):
    """Device cursor and device-level activity state."""

    __tablename__ = "message_devices"

    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="User internal ID")
    user_qiao_id: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="User external ID"
    )

    device_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, comment="Device/installation UUID"
    )

    last_acked_msg_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="Latest acknowledged msg_id_server"
    )

    last_acked_msg_sent_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
        comment="sent_at of last_acked_msg_id (maps to sent_time_ms for cursor ordering)",
    )

    last_pull_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, comment="Latest offline pull timestamp"
    )

    last_seen_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, comment="Latest online/heartbeat timestamp"
    )

    __table_args__ = (
        UniqueConstraint("user_id", "device_id", name="uq_message_devices_user_device"),
        Index("idx_message_devices_user_qiao_id", "user_qiao_id"),
        Index("idx_message_devices_device_id", "device_id"),
        Index("idx_message_devices_last_acked_msg_sent_at", "last_acked_msg_sent_at"),
    )


class MessageEndpoint(SnowflakeModel):
    """Deliverable endpoint binding (provider + lease)."""

    __tablename__ = "message_endpoints"

    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="User internal ID")
    user_qiao_id: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="User external ID"
    )

    endpoint_scope: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        comment="Endpoint scope enum (1=USER, 2=DEVICE)",
    )

    device_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True, comment="Device/installation UUID (DEVICE scope only)"
    )

    provider: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        comment="Transport provider enum (see app.enums.MessageTransportProvider)",
    )

    target_key: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
        comment="Deliver target identifier (websocket=device_id; leancloud=client_id)",
    )

    client_kind: Mapped[int | None] = mapped_column(
        SmallInteger,
        nullable=True,
        comment="Client kind enum (see app.enums.DeviceType)",
    )

    lease_expires_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, comment="Endpoint lease expiry time"
    )

    last_seen_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, comment="Latest presence refresh timestamp"
    )

    __table_args__ = (
        CheckConstraint("provider IN (1, 2)", name="ck_message_endpoints_provider"),
        CheckConstraint("endpoint_scope IN (1, 2)", name="ck_message_endpoints_scope"),
        CheckConstraint(
            "(endpoint_scope = 1 AND device_id IS NULL) OR "
            "(endpoint_scope = 2 AND device_id IS NOT NULL)",
            name="ck_message_endpoints_scope_device",
        ),
        UniqueConstraint(
            "provider",
            "user_id",
            "target_key",
            name="uq_message_endpoints_provider_user_target",
        ),
        Index("idx_message_endpoints_user_qiao_id", "user_qiao_id"),
        Index("idx_message_endpoints_device_id", "device_id"),
        Index("idx_message_endpoints_provider", "provider"),
        Index("idx_message_endpoints_scope", "endpoint_scope"),
        Index("idx_message_endpoints_lease_expires_at", "lease_expires_at"),
        Index(
            "uq_message_endpoints_provider_user_device_scope",
            "provider",
            "user_id",
            "device_id",
            unique=True,
            postgresql_where=text("endpoint_scope = 2"),
        ),
    )


class MessageDelivery(SnowflakeModel):
    """Per-endpoint delivery record."""

    __tablename__ = "message_deliveries"

    msg_id_server: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="References message_history.msg_id_server"
    )

    endpoint_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="Endpoint ID")

    provider: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        comment="Transport provider enum (see app.enums.MessageTransportProvider)",
    )

    target_key: Mapped[str] = mapped_column(
        String(256), nullable=False, comment="Redundant target identifier for audit/debug"
    )

    provider_msg_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="Provider receipt ID (nullable)"
    )

    status: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        comment="Delivery status enum (see app.enums.MessageDeliveryStatus)",
    )

    dispatched_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, comment="Provider dispatched time"
    )

    failed_reason_code: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="Failure reason code"
    )

    failed_detail: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Failure detail/stack"
    )

    __table_args__ = (
        CheckConstraint("provider IN (1, 2)", name="ck_message_deliveries_provider"),
        CheckConstraint("status IN (1, 2, 3)", name="ck_message_deliveries_status"),
        UniqueConstraint("msg_id_server", "endpoint_id", name="uq_message_deliveries_msg_endpoint"),
        Index("idx_message_deliveries_msg_id_server", "msg_id_server"),
        Index("idx_message_deliveries_endpoint_id", "endpoint_id"),
        Index("idx_message_deliveries_status", "status"),
    )


class MessageDispatchOutbox(SnowflakeModel):
    """Dispatch task queue for timeline fanout with retry state."""

    __tablename__ = "message_dispatch_outbox"

    outbox_type: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        comment="Dispatch outbox type enum",
    )

    msg_id_server: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="References message_history.msg_id_server"
    )

    owner_user_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="Owner user ID for endpoint fanout"
    )

    status: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        comment="Dispatch outbox status enum",
    )

    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Retry attempts count"
    )

    next_retry_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, comment="Next retry schedule timestamp"
    )

    locked_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, comment="Current worker lock timestamp"
    )

    last_error_code: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="Last failure reason code"
    )

    last_error_detail: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Last failure detail"
    )

    __table_args__ = (
        UniqueConstraint(
            "outbox_type",
            "msg_id_server",
            name="uq_message_dispatch_outbox_type_msg",
        ),
        CheckConstraint("outbox_type IN (1)", name="ck_message_dispatch_outbox_type"),
        CheckConstraint("status IN (1, 2, 3, 4)", name="ck_message_dispatch_outbox_status"),
        CheckConstraint("attempt_count >= 0", name="ck_message_dispatch_outbox_attempt_count"),
        Index("idx_message_dispatch_outbox_status_next_retry", "status", "next_retry_at"),
        Index("idx_message_dispatch_outbox_owner_user_id", "owner_user_id"),
    )
