"""Align invitation and entitlement schema to the final growth model.

Revision ID: 20260412_00
Revises: 20260411_01
Create Date: 2026-04-12 00:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260412_00"
down_revision: str | Sequence[str] | None = "20260411_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ts_columns() -> list[sa.Column[sa.types.TypeEngine[object]]]:
    return [
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
            comment="Record creation timestamp",
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
            comment="Record last update timestamp",
        ),
    ]


def _created_at_column() -> sa.Column[sa.types.TypeEngine[object]]:
    return sa.Column(
        "created_at",
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("NOW()"),
        comment="Record creation timestamp",
    )


def _create_invitation_and_entitlement_tables() -> None:
    op.create_table(
        "entitlement_types",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
            comment="Auto-increment ID primary key",
        ),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column(
            "mode",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
            comment="Mode: 1=capacity, 2=consumable",
        ),
        sa.Column("unit", sa.String(length=32), nullable=False, server_default=sa.text("'count'")),
        sa.Column(
            "status",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
            comment="Status: 1=active, 2=inactive",
        ),
        *_ts_columns(),
        sa.CheckConstraint("mode IN (1, 2)", name="ck_entitlement_types_mode"),
        sa.CheckConstraint("status IN (1, 2)", name="ck_entitlement_types_status"),
        sa.UniqueConstraint("code", name="uq_entitlement_types_code"),
    )
    op.create_index("idx_entitlement_types_status", "entitlement_types", ["status"], unique=False)

    op.create_table(
        "entitlement_reason_codes",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
            comment="Auto-increment ID primary key",
        ),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=64), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column(
            "status",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
            comment="Status: 1=active, 2=inactive",
        ),
        *_ts_columns(),
        sa.CheckConstraint(
            "code ~ '^[a-z][a-z0-9_]{1,63}$'",
            name="ck_entitlement_reason_codes_code_format",
        ),
        sa.CheckConstraint("status IN (1, 2)", name="ck_entitlement_reason_codes_status"),
        sa.UniqueConstraint("code", name="uq_entitlement_reason_codes_code"),
    )
    op.create_index(
        "idx_entitlement_reason_codes_status",
        "entitlement_reason_codes",
        ["status"],
        unique=False,
    )

    op.create_table(
        "invite_codes",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
            comment="Auto-increment ID primary key",
        ),
        sa.Column("code", sa.String(length=6), nullable=False),
        sa.Column(
            "owner_user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            comment="Owner user id for invite code",
        ),
        sa.Column(
            "status",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
            comment="Status: 1=active, 2=inactive",
        ),
        *_ts_columns(),
        sa.CheckConstraint("status IN (1, 2)", name="ck_invite_codes_status"),
        sa.CheckConstraint("char_length(code) = 6", name="ck_invite_codes_code_len"),
        sa.CheckConstraint("code ~ '^[A-Z0-9]{6}$'", name="ck_invite_codes_code_format"),
        sa.UniqueConstraint("code", name="uq_invite_codes_code"),
        sa.UniqueConstraint("owner_user_id", name="uq_invite_codes_owner_user_id"),
        sa.UniqueConstraint("id", "code", name="uq_invite_codes_id_code"),
        sa.UniqueConstraint("id", "owner_user_id", name="uq_invite_codes_id_owner"),
    )
    op.create_index("idx_invite_codes_status", "invite_codes", ["status"], unique=False)

    op.create_table(
        "invite_bindings",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
            comment="Auto-increment ID primary key",
        ),
        sa.Column(
            "invitee_user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            comment="Invitee user id (bind once)",
        ),
        sa.Column(
            "invite_code_id",
            sa.Integer(),
            sa.ForeignKey("invite_codes.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("code_snapshot", sa.String(length=6), nullable=False, comment="Code snapshot"),
        sa.Column(
            "inviter_user_id_snapshot",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
            comment="Inviter user id snapshot",
        ),
        *_ts_columns(),
        sa.CheckConstraint("char_length(code_snapshot) = 6", name="ck_invite_bindings_code_len"),
        sa.CheckConstraint(
            "code_snapshot ~ '^[A-Z0-9]{6}$'",
            name="ck_invite_bindings_code_format",
        ),
        sa.ForeignKeyConstraint(
            ["invite_code_id", "code_snapshot"],
            ["invite_codes.id", "invite_codes.code"],
            ondelete="RESTRICT",
            name="fk_invite_bindings_code_snapshot_consistent",
        ),
        sa.ForeignKeyConstraint(
            ["invite_code_id", "inviter_user_id_snapshot"],
            ["invite_codes.id", "invite_codes.owner_user_id"],
            ondelete="RESTRICT",
            name="fk_invite_bindings_inviter_snapshot_consistent",
        ),
        sa.UniqueConstraint("invitee_user_id", name="uq_invite_bindings_invitee"),
    )
    op.create_index(
        "idx_invite_bindings_invite_code_id",
        "invite_bindings",
        ["invite_code_id"],
        unique=False,
    )
    op.create_index(
        "idx_invite_bindings_inviter_user",
        "invite_bindings",
        ["inviter_user_id_snapshot"],
        unique=False,
    )

    op.create_table(
        "invite_events",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
            comment="Auto-increment ID primary key",
        ),
        sa.Column(
            "event_type",
            sa.Integer(),
            nullable=False,
            comment="1=open,2=resolve_valid,3=bind_success,4=copy_command,5=share_wechat",
        ),
        sa.Column(
            "actor_user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "invite_code_id",
            sa.Integer(),
            sa.ForeignKey("invite_codes.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "event_source",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'unknown'"),
        ),
        sa.Column("code_snapshot", sa.String(length=6), nullable=True),
        sa.Column("event_payload", sa.JSON(), nullable=True),
        _created_at_column(),
        sa.CheckConstraint("event_type IN (1, 2, 3, 4, 5)", name="ck_invite_events_event_type"),
        sa.CheckConstraint(
            "event_source IN ('login', 'setup', 'link', "
            "'invite_bind_page', 'invite_share_page', 'unknown')",
            name="ck_invite_events_event_source",
        ),
        sa.CheckConstraint(
            "code_snapshot IS NULL OR code_snapshot ~ '^[A-Z0-9]{6}$'",
            name="ck_invite_events_code_snapshot_format",
        ),
    )
    op.create_index(
        "idx_invite_events_code_event_time",
        "invite_events",
        ["invite_code_id", "event_type", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_invite_events_actor_event_time",
        "invite_events",
        ["actor_user_id", "event_type", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_invite_events_type_time",
        "invite_events",
        ["event_type", "created_at"],
        unique=False,
    )

    op.create_table(
        "invite_recognition_logs",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
            comment="Auto-increment ID primary key",
        ),
        sa.Column(
            "actor_user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column(
            "trigger",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'unknown'"),
        ),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("first_candidate", sa.String(length=6), nullable=True),
        sa.Column("recognized_code", sa.String(length=6), nullable=True),
        sa.Column(
            "invite_code_id",
            sa.Integer(),
            sa.ForeignKey("invite_codes.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("valid", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("bindable", sa.Boolean(), nullable=True),
        _created_at_column(),
        sa.CheckConstraint(
            "source IN ('login', 'setup', 'link', 'invite_bind_page', 'invite_share_page')",
            name="ck_invite_recognition_logs_source",
        ),
        sa.CheckConstraint(
            "trigger ~ '^[a-z0-9_\\-]{1,32}$'",
            name="ck_invite_recognition_logs_trigger_format",
        ),
        sa.CheckConstraint(
            "first_candidate IS NULL OR first_candidate ~ '^[A-Z0-9]{6}$'",
            name="ck_invite_recognition_logs_first_candidate_format",
        ),
        sa.CheckConstraint(
            "recognized_code IS NULL OR recognized_code ~ '^[A-Z0-9]{6}$'",
            name="ck_invite_recognition_logs_recognized_code_format",
        ),
    )
    op.create_index(
        "idx_invite_recognition_logs_created_at",
        "invite_recognition_logs",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "idx_invite_recognition_logs_source_created_at",
        "invite_recognition_logs",
        ["source", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_invite_recognition_logs_recognized_code",
        "invite_recognition_logs",
        ["recognized_code"],
        unique=False,
    )

    op.create_table(
        "invite_share_templates",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
            comment="Auto-increment ID primary key",
        ),
        sa.Column("template_text", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
            comment="Status: 1=active, 2=inactive",
        ),
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("100")),
        sa.Column(
            "locale", sa.String(length=16), nullable=False, server_default=sa.text("'zh-CN'")
        ),
        *_ts_columns(),
        sa.CheckConstraint("status IN (1, 2)", name="ck_invite_share_templates_status"),
        sa.CheckConstraint(
            "locale ~ '^[a-z]{2}(\\-[A-Z]{2})?$'",
            name="ck_invite_share_templates_locale_format",
        ),
    )
    op.create_index(
        "idx_invite_share_templates_status_priority",
        "invite_share_templates",
        ["status", "priority", "id"],
        unique=False,
    )
    op.create_index(
        "idx_invite_share_templates_locale",
        "invite_share_templates",
        ["locale"],
        unique=False,
    )

    op.create_table(
        "user_entitlement_accounts",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
            comment="Auto-increment ID primary key",
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "entitlement_type_id",
            sa.Integer(),
            sa.ForeignKey("entitlement_types.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("granted_total", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("used_total", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("available_total", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("0")),
        *_ts_columns(),
        sa.CheckConstraint(
            "granted_total >= 0", name="ck_user_entitlement_accounts_granted_nonnegative"
        ),
        sa.CheckConstraint("used_total >= 0", name="ck_user_entitlement_accounts_used_nonnegative"),
        sa.CheckConstraint(
            "available_total >= 0", name="ck_user_entitlement_accounts_available_nonnegative"
        ),
        sa.CheckConstraint(
            "available_total = granted_total - used_total",
            name="ck_user_entitlement_accounts_available_consistent",
        ),
        sa.UniqueConstraint(
            "user_id",
            "entitlement_type_id",
            name="uq_user_entitlement_accounts_user_type",
        ),
    )
    op.create_index(
        "idx_user_entitlement_accounts_user_id",
        "user_entitlement_accounts",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "idx_user_entitlement_accounts_type_user",
        "user_entitlement_accounts",
        ["entitlement_type_id", "user_id"],
        unique=False,
    )

    op.create_table(
        "user_entitlement_ledger",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
            comment="Auto-increment ID primary key",
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "entitlement_type_id",
            sa.Integer(),
            sa.ForeignKey("entitlement_types.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "action_type",
            sa.Integer(),
            nullable=False,
            comment="Action type: 1=grant, 2=consume, 3=refund, 4=adjust",
        ),
        sa.Column("delta_granted", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("delta_used", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "source_type",
            sa.String(length=32),
            nullable=False,
            comment=(
                "Source type: system_initial/invite_bind_invitee/invite_bind_inviter/"
                "campaign_attribution/redeem_code_claim/contact_ai_slot/"
                "admin_manual_grant/admin_manual_adjust"
            ),
        ),
        sa.Column("source_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "reason_code",
            sa.String(length=64),
            sa.ForeignKey("entitlement_reason_codes.code", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "operator_admin_user_id",
            sa.Integer(),
            sa.ForeignKey("admin_users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("effective_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("event_payload", sa.JSON(), nullable=True),
        _created_at_column(),
        sa.CheckConstraint(
            "action_type IN (1, 2, 3, 4)", name="ck_user_entitlement_ledger_action_type"
        ),
        sa.CheckConstraint(
            "((action_type = 1 AND delta_granted > 0 AND delta_used = 0) OR "
            "(action_type = 2 AND delta_granted = 0 AND delta_used > 0) OR "
            "(action_type = 3 AND delta_granted = 0 AND delta_used < 0) OR "
            "(action_type = 4 AND delta_granted <> 0 AND delta_used = 0))",
            name="ck_user_entitlement_ledger_action_delta_consistent",
        ),
        sa.CheckConstraint(
            "((source_type IN ('admin_manual_grant', 'admin_manual_adjust') "
            "AND reason_code IS NOT NULL AND operator_admin_user_id IS NOT NULL) OR "
            "(source_type NOT IN ('admin_manual_grant', 'admin_manual_adjust') "
            "AND operator_admin_user_id IS NULL))",
            name="ck_user_entitlement_ledger_admin_fields",
        ),
        sa.CheckConstraint(
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
        sa.UniqueConstraint(
            "user_id",
            "entitlement_type_id",
            "idempotency_key",
            name="uq_user_entitlement_ledger_idempotency",
        ),
    )
    op.create_index(
        "idx_user_entitlement_ledger_user_time",
        "user_entitlement_ledger",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_user_entitlement_ledger_type_user_time",
        "user_entitlement_ledger",
        ["entitlement_type_id", "user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_user_entitlement_ledger_source_time",
        "user_entitlement_ledger",
        ["source_type", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_user_entitlement_ledger_reason_time",
        "user_entitlement_ledger",
        ["reason_code", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_user_entitlement_ledger_operator_time",
        "user_entitlement_ledger",
        ["operator_admin_user_id", "created_at"],
        unique=False,
    )


def _create_growth_tables() -> None:
    op.create_table(
        "campaigns",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
            comment="Auto-increment ID primary key",
        ),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column(
            "status",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
            comment="Status: 1=active, 2=inactive",
        ),
        sa.Column("starts_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("ends_at", sa.TIMESTAMP(timezone=True), nullable=True),
        *_ts_columns(),
        sa.CheckConstraint("status IN (1, 2)", name="ck_campaigns_status"),
        sa.CheckConstraint(
            "ends_at IS NULL OR starts_at IS NULL OR ends_at > starts_at",
            name="ck_campaigns_time_range",
        ),
        sa.CheckConstraint("code ~ '^[A-Z0-9_\\-]{3,32}$'", name="ck_campaigns_code_format"),
        sa.UniqueConstraint("code", name="uq_campaigns_code"),
    )
    op.create_index("idx_campaigns_status", "campaigns", ["status"], unique=False)
    op.create_index("idx_campaigns_starts_at", "campaigns", ["starts_at"], unique=False)
    op.create_index("idx_campaigns_ends_at", "campaigns", ["ends_at"], unique=False)

    op.create_table(
        "campaign_attributions",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
            comment="Auto-increment ID primary key",
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "campaign_id",
            sa.Integer(),
            sa.ForeignKey("campaigns.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "attribution_source",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'unknown'"),
        ),
        sa.Column(
            "attributed_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            comment="First-touch attribution time",
        ),
        sa.Column("event_payload", sa.JSON(), nullable=True),
        *_ts_columns(),
        sa.CheckConstraint(
            "attribution_source ~ '^[a-z0-9_\\-]{1,32}$'",
            name="ck_campaign_attributions_source_format",
        ),
        sa.UniqueConstraint("user_id", name="uq_campaign_attributions_user_id"),
    )
    op.create_index(
        "idx_campaign_attributions_campaign_time",
        "campaign_attributions",
        ["campaign_id", "attributed_at"],
        unique=False,
    )
    op.create_index(
        "idx_campaign_attributions_user_time",
        "campaign_attributions",
        ["user_id", "attributed_at"],
        unique=False,
    )

    op.create_table(
        "redeem_code_batches",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
            comment="Auto-increment ID primary key",
        ),
        sa.Column("batch_code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column(
            "status",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
            comment="Status: 1=active, 2=inactive",
        ),
        sa.Column(
            "mode",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
            comment="Redeem code mode: 1=one_time, 2=shared",
        ),
        sa.Column("starts_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("ends_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "budget_total",
            sa.BigInteger(),
            nullable=True,
            comment="Optional budget cap in claims count",
        ),
        sa.Column("budget_used", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "max_claims_per_user",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
            comment="Per-user claim cap for this batch",
        ),
        *_ts_columns(),
        sa.CheckConstraint("status IN (1, 2)", name="ck_redeem_code_batches_status"),
        sa.CheckConstraint("mode IN (1, 2)", name="ck_redeem_code_batches_mode"),
        sa.CheckConstraint(
            "max_claims_per_user > 0", name="ck_redeem_code_batches_claim_cap_positive"
        ),
        sa.CheckConstraint(
            "budget_total IS NULL OR budget_total > 0",
            name="ck_redeem_code_batches_budget_total_positive",
        ),
        sa.CheckConstraint(
            "budget_used >= 0", name="ck_redeem_code_batches_budget_used_nonnegative"
        ),
        sa.CheckConstraint(
            "budget_total IS NULL OR budget_used <= budget_total",
            name="ck_redeem_code_batches_budget_consistent",
        ),
        sa.CheckConstraint(
            "ends_at IS NULL OR starts_at IS NULL OR ends_at > starts_at",
            name="ck_redeem_code_batches_time_range",
        ),
        sa.CheckConstraint(
            "batch_code ~ '^[A-Z0-9_\\-]{3,32}$'", name="ck_redeem_code_batches_code_format"
        ),
        sa.UniqueConstraint("batch_code", name="uq_redeem_code_batches_batch_code"),
    )
    op.create_index(
        "idx_redeem_code_batches_status", "redeem_code_batches", ["status"], unique=False
    )

    op.create_table(
        "redeem_codes",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
            comment="Auto-increment ID primary key",
        ),
        sa.Column(
            "batch_id",
            sa.Integer(),
            sa.ForeignKey("redeem_code_batches.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column(
            "status",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
            comment="Status: 1=active, 2=inactive",
        ),
        sa.Column(
            "max_claims_total",
            sa.Integer(),
            nullable=True,
            comment="Optional max claims count for shared code",
        ),
        sa.Column("claimed_total", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("starts_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("ends_at", sa.TIMESTAMP(timezone=True), nullable=True),
        *_ts_columns(),
        sa.CheckConstraint("status IN (1, 2)", name="ck_redeem_codes_status"),
        sa.CheckConstraint(
            "max_claims_total IS NULL OR max_claims_total > 0",
            name="ck_redeem_codes_claims_total_positive",
        ),
        sa.CheckConstraint("claimed_total >= 0", name="ck_redeem_codes_claimed_total_nonnegative"),
        sa.CheckConstraint(
            "max_claims_total IS NULL OR claimed_total <= max_claims_total",
            name="ck_redeem_codes_claimed_total_consistent",
        ),
        sa.CheckConstraint(
            "ends_at IS NULL OR starts_at IS NULL OR ends_at > starts_at",
            name="ck_redeem_codes_time_range",
        ),
        sa.CheckConstraint("code ~ '^[A-Z0-9\\-]{4,32}$'", name="ck_redeem_codes_code_format"),
        sa.UniqueConstraint("code", name="uq_redeem_codes_code"),
        sa.UniqueConstraint("id", "batch_id", name="uq_redeem_codes_id_batch"),
    )
    op.create_index("idx_redeem_codes_batch_id", "redeem_codes", ["batch_id"], unique=False)
    op.create_index("idx_redeem_codes_status", "redeem_codes", ["status"], unique=False)

    op.create_table(
        "redeem_code_claims",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
            comment="Auto-increment ID primary key",
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "redeem_code_id",
            sa.Integer(),
            sa.ForeignKey("redeem_codes.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "batch_id",
            sa.Integer(),
            sa.ForeignKey("redeem_code_batches.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("code_snapshot", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("event_payload", sa.JSON(), nullable=True),
        _created_at_column(),
        sa.CheckConstraint(
            "code_snapshot ~ '^[A-Z0-9\\-]{4,32}$'", name="ck_redeem_code_claims_code_format"
        ),
        sa.ForeignKeyConstraint(
            ["redeem_code_id", "batch_id"],
            ["redeem_codes.id", "redeem_codes.batch_id"],
            ondelete="RESTRICT",
            name="fk_redeem_code_claims_code_batch_consistent",
        ),
        sa.UniqueConstraint("user_id", "redeem_code_id", name="uq_redeem_code_claims_user_code"),
        sa.UniqueConstraint("idempotency_key", name="uq_redeem_code_claims_idempotency_key"),
    )
    op.create_index(
        "idx_redeem_code_claims_user_time",
        "redeem_code_claims",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_redeem_code_claims_code_time",
        "redeem_code_claims",
        ["redeem_code_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_redeem_code_claims_batch_time",
        "redeem_code_claims",
        ["batch_id", "created_at"],
        unique=False,
    )


def _create_growth_reward_rule_table() -> None:
    op.create_table(
        "growth_reward_rules",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
            comment="Auto-increment ID primary key",
        ),
        sa.Column(
            "trigger_event",
            sa.Integer(),
            nullable=False,
            comment=(
                "Trigger event: 1=invite_bind_success, 2=invitee_setup_completed, "
                "3=campaign_attribution_first_touch, 4=redeem_code_claim_success"
            ),
        ),
        sa.Column(
            "target_role",
            sa.Integer(),
            nullable=False,
            comment="Target role: 1=actor, 2=invitee, 3=inviter",
        ),
        sa.Column(
            "scope_type",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
            comment="Scope type: 1=global, 2=campaign, 3=redeem_batch",
        ),
        sa.Column(
            "scope_id",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment="Scope id: 0 for global; campaign/redeem batch id for scoped rules",
        ),
        sa.Column(
            "entitlement_type_id",
            sa.Integer(),
            sa.ForeignKey("entitlement_types.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "delta_granted",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment="Granted delta value (>0)",
        ),
        sa.Column(
            "max_rewards_per_actor",
            sa.Integer(),
            nullable=True,
            comment="Optional max rewards for one actor under this rule",
        ),
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("100")),
        sa.Column(
            "status",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
            comment="Status: 1=active, 2=inactive",
        ),
        sa.Column("starts_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("ends_at", sa.TIMESTAMP(timezone=True), nullable=True),
        *_ts_columns(),
        sa.CheckConstraint(
            "trigger_event IN (1, 2, 3, 4)", name="ck_growth_reward_rules_trigger_event"
        ),
        sa.CheckConstraint("target_role IN (1, 2, 3)", name="ck_growth_reward_rules_target_role"),
        sa.CheckConstraint("scope_type IN (1, 2, 3)", name="ck_growth_reward_rules_scope_type"),
        sa.CheckConstraint(
            "((scope_type = 1 AND scope_id = 0) OR (scope_type IN (2, 3) AND scope_id > 0))",
            name="ck_growth_reward_rules_scope_id_consistent",
        ),
        sa.CheckConstraint("delta_granted >= 0", name="ck_growth_reward_rules_delta_nonnegative"),
        sa.CheckConstraint(
            "max_rewards_per_actor IS NULL OR max_rewards_per_actor > 0",
            name="ck_growth_reward_rules_max_rewards_positive",
        ),
        sa.CheckConstraint("status IN (1, 2)", name="ck_growth_reward_rules_status"),
        sa.CheckConstraint(
            "ends_at IS NULL OR starts_at IS NULL OR ends_at > starts_at",
            name="ck_growth_reward_rules_time_range",
        ),
        sa.CheckConstraint(
            "(trigger_event <> 1 AND trigger_event <> 2) OR (scope_type = 1)",
            name="ck_growth_reward_rules_invite_scope",
        ),
        sa.CheckConstraint(
            "(trigger_event <> 3) OR (scope_type = 2)", name="ck_growth_reward_rules_campaign_scope"
        ),
        sa.CheckConstraint(
            "(trigger_event <> 4) OR (scope_type = 3)", name="ck_growth_reward_rules_redeem_scope"
        ),
        sa.UniqueConstraint(
            "trigger_event",
            "target_role",
            "scope_type",
            "scope_id",
            "entitlement_type_id",
            "priority",
            name="uq_growth_reward_rules_unique_slot",
        ),
    )
    op.create_index(
        "idx_growth_reward_rules_lookup",
        "growth_reward_rules",
        ["trigger_event", "target_role", "scope_type", "scope_id", "status", "priority"],
        unique=False,
    )
    op.create_index(
        "idx_growth_reward_rules_entitlement_type",
        "growth_reward_rules",
        ["entitlement_type_id"],
        unique=False,
    )


def _create_growth_reward_apply_table() -> None:
    op.create_table(
        "growth_reward_applies",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
            comment="Auto-increment ID primary key",
        ),
        sa.Column(
            "rule_id",
            sa.Integer(),
            sa.ForeignKey("growth_reward_rules.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("trigger_event", sa.Integer(), nullable=False),
        sa.Column("target_role", sa.Integer(), nullable=False),
        sa.Column(
            "actor_user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "beneficiary_user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.BigInteger(), nullable=False),
        sa.Column("scope_type", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("scope_id", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "entitlement_type_id",
            sa.Integer(),
            sa.ForeignKey("entitlement_types.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("delta_granted", sa.BigInteger(), nullable=False),
        sa.Column(
            "ledger_id",
            sa.Integer(),
            sa.ForeignKey("user_entitlement_ledger.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("event_payload", sa.JSON(), nullable=True),
        _created_at_column(),
        sa.CheckConstraint(
            "trigger_event IN (1, 2, 3, 4)",
            name="ck_growth_reward_applies_trigger_event",
        ),
        sa.CheckConstraint(
            "target_role IN (1, 2, 3)",
            name="ck_growth_reward_applies_target_role",
        ),
        sa.CheckConstraint(
            "scope_type IN (1, 2, 3)",
            name="ck_growth_reward_applies_scope_type",
        ),
        sa.CheckConstraint(
            "((scope_type = 1 AND scope_id = 0) OR (scope_type IN (2, 3) AND scope_id > 0))",
            name="ck_growth_reward_applies_scope_id_consistent",
        ),
        sa.CheckConstraint(
            "source_type IN ('invite_bind_invitee', 'invite_bind_inviter', "
            "'campaign_attribution', 'redeem_code_claim')",
            name="ck_growth_reward_applies_source_type",
        ),
        sa.CheckConstraint("source_id > 0", name="ck_growth_reward_applies_source_id_positive"),
        sa.CheckConstraint("delta_granted > 0", name="ck_growth_reward_applies_delta_positive"),
        sa.UniqueConstraint("idempotency_key", name="uq_growth_reward_applies_idempotency_key"),
        sa.UniqueConstraint("ledger_id", name="uq_growth_reward_applies_ledger_id"),
    )
    op.create_index(
        "idx_growth_reward_applies_rule_actor_time",
        "growth_reward_applies",
        ["rule_id", "actor_user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_growth_reward_applies_source",
        "growth_reward_applies",
        ["source_type", "source_id"],
        unique=False,
    )


def _create_operation_material_tables() -> None:
    op.create_table(
        "operation_assets",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
            comment="Auto-increment ID primary key",
        ),
        sa.Column("asset_code", sa.String(length=64), nullable=False),
        sa.Column(
            "media_file_id",
            sa.BigInteger(),
            sa.ForeignKey("media_files.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "asset_type",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
            comment="Asset type: 1=image",
        ),
        sa.Column("cdn_url", sa.String(length=1024), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
            comment="Status: 1=active, 2=inactive",
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "created_by",
            sa.Integer(),
            sa.ForeignKey("admin_users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "updated_by",
            sa.Integer(),
            sa.ForeignKey("admin_users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        *_ts_columns(),
        sa.CheckConstraint("asset_type IN (1)", name="ck_operation_assets_asset_type"),
        sa.CheckConstraint("status IN (1, 2)", name="ck_operation_assets_status"),
        sa.CheckConstraint("version > 0", name="ck_operation_assets_version_positive"),
        sa.CheckConstraint("cdn_url ~ '^https://'", name="ck_operation_assets_cdn_url_https"),
        sa.CheckConstraint("width IS NULL OR width > 0", name="ck_operation_assets_width_positive"),
        sa.CheckConstraint(
            "height IS NULL OR height > 0",
            name="ck_operation_assets_height_positive",
        ),
        sa.UniqueConstraint("asset_code", name="uq_operation_assets_asset_code"),
    )
    op.create_index("idx_operation_assets_status", "operation_assets", ["status"], unique=False)
    op.create_index(
        "idx_operation_assets_media_file",
        "operation_assets",
        ["media_file_id"],
        unique=False,
    )

    op.create_table(
        "operation_slot_configs",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
            comment="Auto-increment ID primary key",
        ),
        sa.Column("slot_code", sa.String(length=64), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("path_template", sa.String(length=512), nullable=False),
        sa.Column(
            "asset_id",
            sa.Integer(),
            sa.ForeignKey("operation_assets.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("100")),
        sa.Column("start_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("end_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
            comment="Status: 1=active, 2=inactive",
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "created_by",
            sa.Integer(),
            sa.ForeignKey("admin_users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "updated_by",
            sa.Integer(),
            sa.ForeignKey("admin_users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        *_ts_columns(),
        sa.CheckConstraint("status IN (1, 2)", name="ck_operation_slot_configs_status"),
        sa.CheckConstraint(
            "slot_code ~ '^[a-z0-9_\\-]{1,64}$'",
            name="ck_operation_slot_configs_slot_code_format",
        ),
        sa.CheckConstraint(
            "channel ~ '^[a-z0-9_\\-]{1,32}$'",
            name="ck_operation_slot_configs_channel_format",
        ),
        sa.CheckConstraint(
            "path_template ~ '^/.+'",
            name="ck_operation_slot_configs_path_template",
        ),
        sa.CheckConstraint(
            "version > 0",
            name="ck_operation_slot_configs_version_positive",
        ),
        sa.CheckConstraint(
            "end_at IS NULL OR start_at IS NULL OR end_at > start_at",
            name="ck_operation_slot_configs_time_range",
        ),
        sa.UniqueConstraint(
            "slot_code",
            "channel",
            "version",
            name="uq_operation_slot_configs_slot_channel_version",
        ),
    )
    op.create_index(
        "idx_operation_slot_configs_lookup",
        "operation_slot_configs",
        ["slot_code", "channel", "status", "priority", "id"],
        unique=False,
    )
    op.create_index(
        "idx_operation_slot_configs_time",
        "operation_slot_configs",
        ["start_at", "end_at"],
        unique=False,
    )

    op.create_table(
        "operation_publish_logs",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
            comment="Auto-increment ID primary key",
        ),
        sa.Column("slot_code", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("from_version", sa.Integer(), nullable=True),
        sa.Column("to_version", sa.Integer(), nullable=False),
        sa.Column(
            "operator_id",
            sa.Integer(),
            sa.ForeignKey("admin_users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reason", sa.String(length=500), nullable=True),
        _created_at_column(),
        sa.CheckConstraint(
            "action IN ('publish', 'rollback')",
            name="ck_operation_publish_logs_action",
        ),
        sa.CheckConstraint(
            "from_version IS NULL OR from_version > 0",
            name="ck_operation_publish_logs_from_version_positive",
        ),
        sa.CheckConstraint(
            "to_version > 0",
            name="ck_operation_publish_logs_to_version_positive",
        ),
    )
    op.create_index(
        "idx_operation_publish_logs_slot_time",
        "operation_publish_logs",
        ["slot_code", "created_at"],
        unique=False,
    )


def _seed_default_invite_share_operation_slot() -> None:
    op.execute(
        """
        INSERT INTO operation_assets (
            asset_code,
            media_file_id,
            asset_type,
            cdn_url,
            mime_type,
            width,
            height,
            status,
            version,
            created_by,
            updated_by
        )
        VALUES (
            'invite_share_card_default',
            NULL,
            1,
            'https://cortex.qiaoqiaoai.cn/share/invite-share-card.png',
            'image/png',
            NULL,
            NULL,
            1,
            1,
            NULL,
            NULL
        )
        ON CONFLICT (asset_code) DO NOTHING
        """
    )

    op.execute(
        """
        INSERT INTO operation_slot_configs (
            slot_code,
            channel,
            title,
            path_template,
            asset_id,
            priority,
            start_at,
            end_at,
            status,
            version,
            created_by,
            updated_by
        )
        SELECT
            'invite_share_card',
            'mini_program',
            '来敲敲AI，对话敲多新奇有趣',
            '/pages/setup/setup?inviteCode={{code}}',
            oa.id,
            100,
            NULL,
            NULL,
            1,
            1,
            NULL,
            NULL
        FROM operation_assets oa
        WHERE oa.asset_code = 'invite_share_card_default'
        ON CONFLICT ON CONSTRAINT uq_operation_slot_configs_slot_channel_version DO NOTHING
        """
    )


def _seed_required_baseline_data() -> None:
    """Seed required environment-independent baseline data for invite/entitlement."""
    op.execute(
        """
        INSERT INTO entitlement_types (code, mode, unit, status)
        VALUES ('ai_contact_limit', 1, 'count', 1)
        ON CONFLICT (code) DO NOTHING
        """
    )

    op.execute(
        """
        INSERT INTO entitlement_reason_codes (code, display_name, description, is_system, status)
        VALUES
            (
                'admin_activity_reward',
                'Activity Reward',
                'Manual grant for activity rewards',
                TRUE,
                1
            ),
            (
                'admin_bug_compensation',
                'Bug Compensation',
                'Manual compensation for bug incidents',
                TRUE,
                1
            ),
            (
                'admin_customer_care',
                'Customer Care',
                'Customer support compensation',
                TRUE,
                1
            ),
            (
                'admin_ops_correction',
                'Ops Correction',
                'Operational correction for entitlement data',
                TRUE,
                1
            )
        ON CONFLICT (code) DO NOTHING
        """
    )

    op.execute(
        """
        INSERT INTO growth_reward_rules (
            trigger_event,
            target_role,
            scope_type,
            scope_id,
            entitlement_type_id,
            delta_granted,
            max_rewards_per_actor,
            priority,
            status
        )
        SELECT 1, 2, 1, 0, et.id, 1, NULL, 100, 1
        FROM entitlement_types et
        WHERE et.code = 'ai_contact_limit'
        ON CONFLICT ON CONSTRAINT uq_growth_reward_rules_unique_slot DO NOTHING
        """
    )

    op.execute(
        """
        INSERT INTO growth_reward_rules (
            trigger_event,
            target_role,
            scope_type,
            scope_id,
            entitlement_type_id,
            delta_granted,
            max_rewards_per_actor,
            priority,
            status
        )
        SELECT 2, 3, 1, 0, et.id, 1, 3, 100, 1
        FROM entitlement_types et
        WHERE et.code = 'ai_contact_limit'
        ON CONFLICT ON CONSTRAINT uq_growth_reward_rules_unique_slot DO NOTHING
        """
    )

    op.execute(
        """
        INSERT INTO invite_share_templates (template_text, status, priority, locale)
        VALUES
            ('文案 {{code}} {{link}}', 1, 100, 'zh-CN'),
            ('敲敲好友都在用，{{code}} {{link}}', 1, 100, 'zh-CN'),
            ('一起用敲敲，{{code}} {{link}}', 1, 100, 'zh-CN')
        """
    )

    op.execute(
        """
        INSERT INTO system_configs (
            config_key,
            config_value,
            default_value,
            config_type,
            description,
            group_name,
            allowed_values
        )
        VALUES
            (
                'contacts_initial_ai_contact_limit',
                '1',
                '1',
                2,
                'Initial AI contact limit for new users (snapshotted at user creation).',
                'contacts',
                NULL
            ),
            (
                'invite_code_resolve_rate_limit_requests',
                '20',
                '20',
                2,
                'Invite code resolve rate limit requests',
                'invitations',
                NULL
            ),
            (
                'invite_code_resolve_rate_limit_window_seconds',
                '60',
                '60',
                2,
                'Invite code resolve rate limit window in seconds',
                'invitations',
                NULL
            ),
            (
                'invite_code_bind_rate_limit_requests',
                '10',
                '10',
                2,
                'Invite code bind rate limit requests',
                'invitations',
                NULL
            ),
            (
                'invite_code_bind_rate_limit_window_seconds',
                '60',
                '60',
                2,
                'Invite code bind rate limit window in seconds',
                'invitations',
                NULL
            )
        ON CONFLICT (config_key) DO NOTHING
        """
    )

    op.execute(
        """
        WITH entitlement AS (
            SELECT id AS entitlement_type_id
            FROM entitlement_types
            WHERE code = 'ai_contact_limit'
            LIMIT 1
        ),
        config AS (
            SELECT COALESCE(
                (
                    SELECT CASE
                        WHEN sc.config_value ~ '^[0-9]+$' THEN GREATEST(sc.config_value::bigint, 1)
                        ELSE 1
                    END
                    FROM system_configs sc
                    WHERE sc.config_key = 'contacts_initial_ai_contact_limit'
                    LIMIT 1
                ),
                1
            )::bigint AS initial_limit
        ),
        user_ai_contacts AS (
            SELECT
                u.id AS user_id,
                COALESCE(
                    COUNT(c.id) FILTER (
                        WHERE c.contact_type = 2
                          AND c.is_deleted = 0
                    ),
                    0
                )::bigint AS active_ai_contacts
            FROM users u
            LEFT JOIN contacts c ON c.user_id = u.id
            GROUP BY u.id
        ),
        seed AS (
            SELECT
                uc.user_id,
                et.entitlement_type_id,
                GREATEST(cfg.initial_limit, uc.active_ai_contacts) AS granted_total,
                uc.active_ai_contacts AS used_total
            FROM user_ai_contacts uc
            CROSS JOIN entitlement et
            CROSS JOIN config cfg
        ),
        inserted_accounts AS (
            INSERT INTO user_entitlement_accounts (
                user_id,
                entitlement_type_id,
                granted_total,
                used_total,
                available_total,
                version
            )
            SELECT
                s.user_id,
                s.entitlement_type_id,
                s.granted_total,
                s.used_total,
                s.granted_total - s.used_total,
                0
            FROM seed s
            ON CONFLICT (user_id, entitlement_type_id) DO NOTHING
            RETURNING
                user_id,
                entitlement_type_id,
                granted_total
        )
        INSERT INTO user_entitlement_ledger (
            user_id,
            entitlement_type_id,
            action_type,
            delta_granted,
            delta_used,
            source_type,
            source_id,
            reason_code,
            operator_admin_user_id,
            idempotency_key,
            effective_at,
            event_payload
        )
        SELECT
            ia.user_id,
            ia.entitlement_type_id,
            1,
            ia.granted_total,
            0,
            'system_initial',
            0,
            NULL,
            NULL,
            'system_initial:0',
            NOW(),
            '{"seed":"migration_20260412_00_backfill"}'::json
        FROM inserted_accounts ia
        WHERE ia.granted_total > 0
        ON CONFLICT (user_id, entitlement_type_id, idempotency_key) DO NOTHING
        """
    )


def upgrade() -> None:
    """Apply invitation and entitlement growth schema."""
    _create_invitation_and_entitlement_tables()
    _create_growth_tables()
    _create_growth_reward_rule_table()
    _create_growth_reward_apply_table()
    _create_operation_material_tables()
    _seed_required_baseline_data()
    _seed_default_invite_share_operation_slot()


def downgrade() -> None:
    """Downgrade is intentionally unsupported for this migration."""
    raise RuntimeError("Downgrade is not supported for migration 20260412_00")
