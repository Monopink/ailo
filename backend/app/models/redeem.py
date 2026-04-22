"""Redeem code related models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AutoIncrementModel, ImmutableAutoIncrementModel


class RedeemCodeBatch(AutoIncrementModel):
    """Redeem code batch configuration."""

    __tablename__ = "redeem_code_batches"

    batch_code: Mapped[str] = mapped_column(
        String(32), nullable=False, unique=True, comment="Batch code"
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False, comment="Batch name")
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, comment="Status: 1=active, 2=inactive"
    )
    mode: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, comment="Redeem code mode: 1=one_time, 2=shared"
    )
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    budget_total: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="Optional budget cap in claims count"
    )
    budget_used: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    max_claims_per_user: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, comment="Per-user claim cap for this batch"
    )

    __table_args__ = (
        CheckConstraint("status IN (1, 2)", name="ck_redeem_code_batches_status"),
        CheckConstraint("mode IN (1, 2)", name="ck_redeem_code_batches_mode"),
        CheckConstraint(
            "max_claims_per_user > 0", name="ck_redeem_code_batches_claim_cap_positive"
        ),
        CheckConstraint(
            "budget_total IS NULL OR budget_total > 0",
            name="ck_redeem_code_batches_budget_total_positive",
        ),
        CheckConstraint("budget_used >= 0", name="ck_redeem_code_batches_budget_used_nonnegative"),
        CheckConstraint(
            "budget_total IS NULL OR budget_used <= budget_total",
            name="ck_redeem_code_batches_budget_consistent",
        ),
        CheckConstraint(
            "ends_at IS NULL OR starts_at IS NULL OR ends_at > starts_at",
            name="ck_redeem_code_batches_time_range",
        ),
        CheckConstraint(
            "batch_code ~ '^[A-Z0-9_\\-]{3,32}$'",
            name="ck_redeem_code_batches_code_format",
        ),
        UniqueConstraint("batch_code", name="uq_redeem_code_batches_batch_code"),
        Index("idx_redeem_code_batches_status", "status"),
    )


class RedeemCode(AutoIncrementModel):
    """Redeem code entity."""

    __tablename__ = "redeem_codes"

    batch_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("redeem_code_batches.id", ondelete="RESTRICT"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    status: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, comment="Status: 1=active, 2=inactive"
    )
    max_claims_total: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Optional max claims count for shared code"
    )
    claimed_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    batch = relationship("RedeemCodeBatch", foreign_keys=[batch_id], lazy="raise", viewonly=True)

    __table_args__ = (
        CheckConstraint("status IN (1, 2)", name="ck_redeem_codes_status"),
        CheckConstraint(
            "max_claims_total IS NULL OR max_claims_total > 0",
            name="ck_redeem_codes_claims_total_positive",
        ),
        CheckConstraint("claimed_total >= 0", name="ck_redeem_codes_claimed_total_nonnegative"),
        CheckConstraint(
            "max_claims_total IS NULL OR claimed_total <= max_claims_total",
            name="ck_redeem_codes_claimed_total_consistent",
        ),
        CheckConstraint(
            "ends_at IS NULL OR starts_at IS NULL OR ends_at > starts_at",
            name="ck_redeem_codes_time_range",
        ),
        CheckConstraint("code ~ '^[A-Z0-9\\-]{4,32}$'", name="ck_redeem_codes_code_format"),
        UniqueConstraint("code", name="uq_redeem_codes_code"),
        UniqueConstraint("id", "batch_id", name="uq_redeem_codes_id_batch"),
        Index("idx_redeem_codes_batch_id", "batch_id"),
        Index("idx_redeem_codes_status", "status"),
    )


class RedeemCodeClaim(ImmutableAutoIncrementModel):
    """Redeem code claim record."""

    __tablename__ = "redeem_code_claims"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    redeem_code_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("redeem_codes.id", ondelete="RESTRICT"), nullable=False
    )
    batch_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("redeem_code_batches.id", ondelete="RESTRICT"), nullable=False
    )
    code_snapshot: Mapped[str] = mapped_column(String(32), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    event_payload: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)

    user = relationship("User", foreign_keys=[user_id], lazy="raise", viewonly=True)
    redeem_code = relationship(
        "RedeemCode", foreign_keys=[redeem_code_id], lazy="raise", viewonly=True
    )
    batch = relationship("RedeemCodeBatch", foreign_keys=[batch_id], lazy="raise", viewonly=True)

    __table_args__ = (
        CheckConstraint(
            "code_snapshot ~ '^[A-Z0-9\\-]{4,32}$'", name="ck_redeem_code_claims_code_format"
        ),
        ForeignKeyConstraint(
            ["redeem_code_id", "batch_id"],
            ["redeem_codes.id", "redeem_codes.batch_id"],
            ondelete="RESTRICT",
            name="fk_redeem_code_claims_code_batch_consistent",
        ),
        UniqueConstraint("user_id", "redeem_code_id", name="uq_redeem_code_claims_user_code"),
        UniqueConstraint("idempotency_key", name="uq_redeem_code_claims_idempotency_key"),
        Index("idx_redeem_code_claims_user_time", "user_id", "created_at"),
        Index("idx_redeem_code_claims_code_time", "redeem_code_id", "created_at"),
        Index("idx_redeem_code_claims_batch_time", "batch_id", "created_at"),
    )
