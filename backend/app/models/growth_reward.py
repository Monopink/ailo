"""Growth reward rule model."""

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
    and_,
    text,
)
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.models.base import AutoIncrementModel, ImmutableAutoIncrementModel
from app.models.campaign import Campaign
from app.models.redeem import RedeemCodeBatch

SCOPE_TYPE_CAMPAIGN = 2
SCOPE_TYPE_REDEEM_BATCH = 3


class GrowthRewardRule(AutoIncrementModel):
    """Unified reward rule table for invite/attribution/redeem triggers."""

    __tablename__ = "growth_reward_rules"

    trigger_event: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment=(
            "Trigger event: 1=invite_bind_success, "
            "3=campaign_attribution_first_touch, 4=redeem_code_claim_success"
        ),
    )
    target_role: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Target role: 1=actor, 2=invitee, 3=inviter"
    )
    scope_type: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Scope type: 1=global, 2=campaign, 3=redeem_batch",
    )
    scope_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Scope id: 0 for global; campaign/redeem batch id for scoped rules",
    )
    entitlement_type_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("entitlement_types.id", ondelete="RESTRICT"), nullable=False
    )
    delta_granted: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Granted delta value (>0)"
    )
    max_rewards_per_actor: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Optional max rewards for one actor under this rule",
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    status: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, comment="Status: 1=active, 2=inactive"
    )
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    entitlement_type = relationship(
        "EntitlementType", foreign_keys=[entitlement_type_id], lazy="raise", viewonly=True
    )
    campaign = relationship(
        "Campaign",
        primaryjoin=lambda: and_(
            foreign(GrowthRewardRule.scope_id) == Campaign.id,
            GrowthRewardRule.scope_type == SCOPE_TYPE_CAMPAIGN,
        ),
        viewonly=True,
        lazy="raise",
    )
    redeem_batch = relationship(
        "RedeemCodeBatch",
        primaryjoin=lambda: and_(
            foreign(GrowthRewardRule.scope_id) == RedeemCodeBatch.id,
            GrowthRewardRule.scope_type == SCOPE_TYPE_REDEEM_BATCH,
        ),
        viewonly=True,
        lazy="raise",
    )

    __table_args__ = (
        CheckConstraint("trigger_event IN (1, 3, 4)", name="ck_growth_reward_rules_trigger_event"),
        CheckConstraint("target_role IN (1, 2, 3)", name="ck_growth_reward_rules_target_role"),
        CheckConstraint("scope_type IN (1, 2, 3)", name="ck_growth_reward_rules_scope_type"),
        CheckConstraint(
            "((scope_type = 1 AND scope_id = 0) OR (scope_type IN (2, 3) AND scope_id > 0))",
            name="ck_growth_reward_rules_scope_id_consistent",
        ),
        CheckConstraint("delta_granted >= 0", name="ck_growth_reward_rules_delta_nonnegative"),
        CheckConstraint(
            "max_rewards_per_actor IS NULL OR max_rewards_per_actor > 0",
            name="ck_growth_reward_rules_max_rewards_positive",
        ),
        CheckConstraint("status IN (1, 2)", name="ck_growth_reward_rules_status"),
        CheckConstraint(
            "ends_at IS NULL OR starts_at IS NULL OR ends_at > starts_at",
            name="ck_growth_reward_rules_time_range",
        ),
        CheckConstraint(
            "(trigger_event <> 1) OR (scope_type = 1)",
            name="ck_growth_reward_rules_invite_scope",
        ),
        CheckConstraint(
            "(trigger_event <> 3) OR (scope_type = 2)",
            name="ck_growth_reward_rules_campaign_scope",
        ),
        CheckConstraint(
            "(trigger_event <> 4) OR (scope_type = 3)",
            name="ck_growth_reward_rules_redeem_scope",
        ),
        UniqueConstraint(
            "trigger_event",
            "target_role",
            "scope_type",
            "scope_id",
            "entitlement_type_id",
            "priority",
            name="uq_growth_reward_rules_unique_slot",
        ),
        Index(
            "idx_growth_reward_rules_lookup",
            "trigger_event",
            "target_role",
            "scope_type",
            "scope_id",
            "status",
            "priority",
        ),
        Index(
            "uq_growth_reward_rules_active_invite_slot",
            "trigger_event",
            "target_role",
            "scope_type",
            "scope_id",
            "entitlement_type_id",
            unique=True,
            postgresql_where=text(
                "status = 1 AND trigger_event = 1 AND target_role IN (2, 3) "
                "AND scope_type = 1 AND scope_id = 0"
            ),
        ),
        Index("idx_growth_reward_rules_entitlement_type", "entitlement_type_id"),
    )


class GrowthRewardApply(ImmutableAutoIncrementModel):
    """Structured reward apply records for limits/statistics and audit."""

    __tablename__ = "growth_reward_applies"

    rule_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("growth_reward_rules.id", ondelete="RESTRICT"),
        nullable=False,
    )
    trigger_event: Mapped[int] = mapped_column(Integer, nullable=False)
    target_role: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    beneficiary_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    scope_type: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    scope_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    entitlement_type_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("entitlement_types.id", ondelete="RESTRICT"),
        nullable=False,
    )
    delta_granted: Mapped[int] = mapped_column(BigInteger, nullable=False)
    ledger_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_entitlement_ledger.id", ondelete="CASCADE"),
        nullable=False,
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    event_payload: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)

    rule = relationship("GrowthRewardRule", foreign_keys=[rule_id], lazy="raise", viewonly=True)
    actor_user = relationship("User", foreign_keys=[actor_user_id], lazy="raise", viewonly=True)
    beneficiary_user = relationship(
        "User", foreign_keys=[beneficiary_user_id], lazy="raise", viewonly=True
    )
    entitlement_type = relationship(
        "EntitlementType", foreign_keys=[entitlement_type_id], lazy="raise", viewonly=True
    )
    ledger = relationship(
        "UserEntitlementLedger",
        foreign_keys=[ledger_id],
        lazy="raise",
        viewonly=True,
    )

    __table_args__ = (
        CheckConstraint(
            "trigger_event IN (1, 3, 4)",
            name="ck_growth_reward_applies_trigger_event",
        ),
        CheckConstraint(
            "target_role IN (1, 2, 3)",
            name="ck_growth_reward_applies_target_role",
        ),
        CheckConstraint(
            "scope_type IN (1, 2, 3)",
            name="ck_growth_reward_applies_scope_type",
        ),
        CheckConstraint(
            "((scope_type = 1 AND scope_id = 0) OR (scope_type IN (2, 3) AND scope_id > 0))",
            name="ck_growth_reward_applies_scope_id_consistent",
        ),
        CheckConstraint(
            "source_type IN ('invite_bind_invitee', 'invite_bind_inviter', "
            "'campaign_attribution', 'redeem_code_claim')",
            name="ck_growth_reward_applies_source_type",
        ),
        CheckConstraint("source_id > 0", name="ck_growth_reward_applies_source_id_positive"),
        CheckConstraint(
            "delta_granted > 0",
            name="ck_growth_reward_applies_delta_positive",
        ),
        UniqueConstraint("idempotency_key", name="uq_growth_reward_applies_idempotency_key"),
        UniqueConstraint("ledger_id", name="uq_growth_reward_applies_ledger_id"),
        Index(
            "idx_growth_reward_applies_rule_actor_time",
            "rule_id",
            "actor_user_id",
            "created_at",
        ),
        Index("idx_growth_reward_applies_source", "source_type", "source_id"),
    )
