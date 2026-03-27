"""Alerting system models.

This module defines audit-only business alert event tables:
- alert_events
- alert_event_entities
"""

from sqlalchemy import BigInteger, CheckConstraint, Index, SmallInteger, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import ImmutableSnowflakeModel
from app.type_defs import JSONDict


class AlertEvent(ImmutableSnowflakeModel):
    """Audit-only business alert event."""

    __tablename__ = "alert_events"

    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    domain: Mapped[str] = mapped_column(String(40), nullable=False)
    severity_level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    dedupe_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    details: Mapped[JSONDict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "severity_level IN (10, 20, 30, 40, 50)",
            name="ck_alert_events_severity_level",
        ),
        Index("idx_alert_events_event_type_created_at", "event_type", "created_at"),
        Index("idx_alert_events_domain_created_at", "domain", "created_at"),
        Index("idx_alert_events_created_at", "created_at"),
        Index("idx_alert_events_dedupe_key", "dedupe_key"),
        Index(
            "uq_alert_events_event_type_dedupe_key",
            "event_type",
            "dedupe_key",
            unique=True,
            postgresql_where=(dedupe_key.isnot(None)),
        ),
    )


class AlertEventEntity(ImmutableSnowflakeModel):
    """Audit-only alert event entity reference."""

    __tablename__ = "alert_event_entities"

    event_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(128), nullable=False)

    __table_args__ = (
        Index("idx_alert_event_entities_event_id", "event_id"),
        Index(
            "idx_alert_event_entities_type_id_created_at",
            "entity_type",
            "entity_id",
            "created_at",
        ),
    )


__all__ = ["AlertEvent", "AlertEventEntity"]
