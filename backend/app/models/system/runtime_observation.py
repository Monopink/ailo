"""Client runtime observation models."""

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import ImmutableSnowflakeModel


class ClientRuntimeObservation(ImmutableSnowflakeModel):
    """Immutable client runtime observation event."""

    __tablename__ = "client_runtime_observations"

    client_type: Mapped[str] = mapped_column(String(32), nullable=False)
    device_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    user_agent: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    platform: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    os_version: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    app_version: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    build_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    build_time: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    network_type: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    scope_snapshot: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    feature_hits: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    ua_fetch_status: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    event_name: Mapped[str] = mapped_column(String(64), nullable=False)
    page_path: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    entry_source: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    event_payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    event_payload_digest: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    request_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    occurred_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "scope_snapshot IN (0, 1)",
            name="ck_client_runtime_observations_scope_snapshot",
        ),
        CheckConstraint(
            "ua_fetch_status IN (0, 1, 2, 3)",
            name="ck_client_runtime_observations_ua_fetch_status",
        ),
        Index(
            "idx_client_runtime_observations_client_time",
            "client_type",
            "occurred_at",
        ),
        Index(
            "idx_client_runtime_observations_device_event_time",
            "device_id",
            "event_name",
            "occurred_at",
        ),
        Index(
            "idx_client_runtime_observations_scope_time",
            "scope_snapshot",
            "occurred_at",
        ),
        Index(
            "idx_client_runtime_observations_session_time",
            "session_id",
            "occurred_at",
        ),
    )


__all__ = ["ClientRuntimeObservation"]
