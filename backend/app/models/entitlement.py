"""Entitlement models.

Defines entitlement dictionaries, user entitlement accounts, and immutable ledger.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AutoIncrementModel, ImmutableAutoIncrementModel


class EntitlementType(AutoIncrementModel):
    """Entitlement type dictionary."""

    __tablename__ = "entitlement_types"

    code: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, comment="Entitlement code (e.g., ai_contact_limit)"
    )
    mode: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, comment="Mode: 1=capacity, 2=consumable"
    )
    unit: Mapped[str] = mapped_column(String(32), nullable=False, default="count")
    status: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, comment="Status: 1=active, 2=inactive"
    )

    __table_args__ = (
        CheckConstraint("mode IN (1, 2)", name="ck_entitlement_types_mode"),
        CheckConstraint("status IN (1, 2)", name="ck_entitlement_types_status"),
        Index("idx_entitlement_types_status", "status"),
    )


class EntitlementReasonCode(AutoIncrementModel):
    """Reason code dictionary used by manual/admin operations."""

    __tablename__ = "entitlement_reason_codes"

    code: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, comment="Reason code for entitlement operation"
    )
    display_name: Mapped[str] = mapped_column(String(64), nullable=False, comment="Display name")
    description: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="Optional reason description"
    )
    applies_to: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="both",
        comment="Allowed operation type: grant/adjust/both",
    )
    is_system: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="Built-in reason code flag"
    )
    status: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, comment="Status: 1=active, 2=inactive"
    )

    __table_args__ = (
        CheckConstraint(
            "code ~ '^[a-z][a-z0-9_]{1,63}$'",
            name="ck_entitlement_reason_codes_code_format",
        ),
        CheckConstraint(
            "applies_to IN ('grant', 'adjust', 'both')",
            name="ck_entitlement_reason_codes_applies_to",
        ),
        CheckConstraint("status IN (1, 2)", name="ck_entitlement_reason_codes_status"),
        Index("idx_entitlement_reason_codes_status", "status"),
        Index("idx_entitlement_reason_codes_applies_to", "applies_to"),
    )


class UserEntitlementAccount(AutoIncrementModel):
    """User entitlement account snapshot for read path."""

    __tablename__ = "user_entitlement_accounts"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    entitlement_type_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("entitlement_types.id", ondelete="RESTRICT"), nullable=False
    )
    granted_total: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    used_total: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    available_total: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    user = relationship("User", foreign_keys=[user_id], lazy="raise", viewonly=True)
    entitlement_type = relationship(
        "EntitlementType", foreign_keys=[entitlement_type_id], lazy="raise", viewonly=True
    )

    __table_args__ = (
        CheckConstraint(
            "granted_total >= 0", name="ck_user_entitlement_accounts_granted_nonnegative"
        ),
        CheckConstraint("used_total >= 0", name="ck_user_entitlement_accounts_used_nonnegative"),
        CheckConstraint(
            "available_total >= 0", name="ck_user_entitlement_accounts_available_nonnegative"
        ),
        CheckConstraint(
            "available_total = granted_total - used_total",
            name="ck_user_entitlement_accounts_available_consistent",
        ),
        UniqueConstraint(
            "user_id",
            "entitlement_type_id",
            name="uq_user_entitlement_accounts_user_type",
        ),
        Index("idx_user_entitlement_accounts_user_id", "user_id"),
        Index("idx_user_entitlement_accounts_type_user", "entitlement_type_id", "user_id"),
    )


class UserEntitlementLedger(ImmutableAutoIncrementModel):
    """Immutable entitlement ledger."""

    __tablename__ = "user_entitlement_ledger"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    entitlement_type_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("entitlement_types.id", ondelete="RESTRICT"), nullable=False
    )
    action_type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Action type: 1=grant, 2=consume, 3=refund, 4=adjust"
    )
    delta_granted: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    delta_used: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    source_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment=(
            "Source type: system_initial/invite_bind_invitee/invite_bind_inviter/"
            "campaign_attribution/redeem_code_claim/contact_ai_slot/"
            "admin_manual_grant/admin_manual_adjust"
        ),
    )
    source_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reason_code: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("entitlement_reason_codes.code", ondelete="RESTRICT"),
        nullable=True,
    )
    operator_admin_user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    event_payload: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)

    user = relationship("User", foreign_keys=[user_id], lazy="raise", viewonly=True)
    entitlement_type = relationship(
        "EntitlementType", foreign_keys=[entitlement_type_id], lazy="raise", viewonly=True
    )
    reason_code_ref = relationship(
        "EntitlementReasonCode", foreign_keys=[reason_code], lazy="raise", viewonly=True
    )
    operator_admin_user = relationship(
        "AdminUser", foreign_keys=[operator_admin_user_id], lazy="raise", viewonly=True
    )

    __table_args__ = (
        CheckConstraint(
            "action_type IN (1, 2, 3, 4)", name="ck_user_entitlement_ledger_action_type"
        ),
        CheckConstraint(
            "((action_type = 1 AND delta_granted > 0 AND delta_used = 0) OR "
            "(action_type = 2 AND delta_granted = 0 AND delta_used > 0) OR "
            "(action_type = 3 AND delta_granted = 0 AND delta_used < 0) OR "
            "(action_type = 4 AND delta_granted <> 0 AND delta_used = 0))",
            name="ck_user_entitlement_ledger_action_delta_consistent",
        ),
        CheckConstraint(
            "((source_type IN ('admin_manual_grant', 'admin_manual_adjust') "
            "AND reason_code IS NOT NULL AND operator_admin_user_id IS NOT NULL) OR "
            "(source_type NOT IN ('admin_manual_grant', 'admin_manual_adjust') "
            "AND operator_admin_user_id IS NULL))",
            name="ck_user_entitlement_ledger_admin_fields",
        ),
        CheckConstraint(
            "source_type IN ("
            "'system_initial',"
            "'invite_bind_invitee',"
            "'invite_bind_inviter',"
            "'campaign_attribution',"
            "'redeem_code_claim',"
            "'contact_ai_slot',"
            "'admin_manual_grant',"
            "'admin_manual_adjust'"
            ")",
            name="ck_user_entitlement_ledger_source_type",
        ),
        UniqueConstraint(
            "user_id",
            "entitlement_type_id",
            "idempotency_key",
            name="uq_user_entitlement_ledger_idempotency",
        ),
        Index("idx_user_entitlement_ledger_user_time", "user_id", "created_at"),
        Index(
            "idx_user_entitlement_ledger_type_user_time",
            "entitlement_type_id",
            "user_id",
            "created_at",
        ),
        Index(
            "idx_user_entitlement_ledger_source_time",
            "source_type",
            "created_at",
        ),
        Index(
            "idx_user_entitlement_ledger_reason_time",
            "reason_code",
            "created_at",
        ),
        Index(
            "idx_user_entitlement_ledger_operator_time",
            "operator_admin_user_id",
            "created_at",
        ),
    )
