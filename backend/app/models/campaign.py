"""Campaign related models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AutoIncrementModel


class Campaign(AutoIncrementModel):
    """Campaign metadata for first-touch attribution."""

    __tablename__ = "campaigns"

    code: Mapped[str] = mapped_column(
        String(32), nullable=False, unique=True, comment="Campaign code for attribution"
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False, comment="Campaign name")
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, comment="Status: 1=active, 2=inactive"
    )
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("status IN (1, 2)", name="ck_campaigns_status"),
        CheckConstraint(
            "ends_at IS NULL OR starts_at IS NULL OR ends_at > starts_at",
            name="ck_campaigns_time_range",
        ),
        CheckConstraint("code ~ '^[A-Z0-9_\\-]{3,32}$'", name="ck_campaigns_code_format"),
        UniqueConstraint("code", name="uq_campaigns_code"),
        Index("idx_campaigns_status", "status"),
        Index("idx_campaigns_starts_at", "starts_at"),
        Index("idx_campaigns_ends_at", "ends_at"),
    )


class CampaignAttribution(AutoIncrementModel):
    """First-touch campaign attribution per user."""

    __tablename__ = "campaign_attributions"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    campaign_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("campaigns.id", ondelete="RESTRICT"), nullable=False
    )
    attribution_source: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    attributed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="First-touch attribution time"
    )
    event_payload: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)

    user = relationship("User", foreign_keys=[user_id], lazy="raise", viewonly=True)
    campaign = relationship("Campaign", foreign_keys=[campaign_id], lazy="raise", viewonly=True)

    __table_args__ = (
        CheckConstraint(
            "attribution_source ~ '^[a-z0-9_\\-]{1,32}$'",
            name="ck_campaign_attributions_source_format",
        ),
        UniqueConstraint("user_id", name="uq_campaign_attributions_user_id"),
        Index("idx_campaign_attributions_campaign_time", "campaign_id", "attributed_at"),
        Index("idx_campaign_attributions_user_time", "user_id", "attributed_at"),
    )
