"""Add contact request retry attempts event table.

Revision ID: 20260522_01
Revises: 20260516_01
Create Date: 2026-05-22 16:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260522_01"
down_revision: str | Sequence[str] | None = "20260516_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create contact request retry attempts event table."""
    op.create_table(
        "contact_request_retry_attempts",
        sa.Column("id", sa.BigInteger(), nullable=False, comment="Snowflake ID primary key"),
        sa.Column("request_id", sa.BigInteger(), nullable=False, comment="contact_requests.id"),
        sa.Column(
            "attempt_no",
            sa.Integer(),
            nullable=False,
            comment="Monotonic retry attempt number per request",
        ),
        sa.Column(
            "operator_admin_user_id",
            sa.Integer(),
            nullable=True,
            comment="Admin user id who triggered retry",
        ),
        sa.Column(
            "operator_username",
            sa.String(length=64),
            nullable=True,
            comment="Admin username who triggered retry",
        ),
        sa.Column(
            "mode",
            sa.String(length=16),
            nullable=False,
            comment="Retry mode: AUTO or TEMPLATE",
        ),
        sa.Column(
            "selected_template_id",
            sa.Integer(),
            nullable=True,
            comment="Explicitly selected ai_templates.id for TEMPLATE mode",
        ),
        sa.Column(
            "force_continue",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Whether operator force-continued despite warnings",
        ),
        sa.Column(
            "idempotency_key",
            sa.String(length=128),
            nullable=False,
            comment="Idempotency key for admin retry execution",
        ),
        sa.Column(
            "precheck_checks",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="Precheck checks snapshot",
        ),
        sa.Column(
            "precheck_warnings",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="Precheck warnings snapshot",
        ),
        sa.Column(
            "precheck_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Precheck summary snapshot",
        ),
        sa.Column(
            "requested_ai_type_id",
            sa.Integer(),
            nullable=True,
            comment="Requested target ai type id from pending request",
        ),
        sa.Column(
            "selected_template_type_id",
            sa.Integer(),
            nullable=True,
            comment="Actual selected template type id",
        ),
        sa.Column(
            "is_type_mismatch",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Whether requested and selected template types mismatch",
        ),
        sa.Column(
            "result_status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'FAILED'"),
            comment="Result status: SUCCESS, FAILED, REJECTED, ERROR",
        ),
        sa.Column(
            "result_failure_code",
            sa.String(length=64),
            nullable=True,
            comment="Failure code after retry execution",
        ),
        sa.Column(
            "result_failure_detail",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Failure detail snapshot after retry execution",
        ),
        sa.Column(
            "started_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            comment="Retry attempt started at",
        ),
        sa.Column(
            "finished_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
            comment="Retry attempt finished at",
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
            comment="Record creation timestamp",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "request_id",
            "attempt_no",
            name="uq_contact_request_retry_attempt_request_attempt_no",
        ),
        sa.UniqueConstraint(
            "request_id",
            "idempotency_key",
            name="uq_contact_request_retry_attempt_request_idempotency",
        ),
    )
    op.create_index(
        "idx_contact_request_retry_attempts_request_id",
        "contact_request_retry_attempts",
        ["request_id"],
        unique=False,
    )
    op.create_index(
        "idx_contact_request_retry_attempts_started_at",
        "contact_request_retry_attempts",
        ["started_at"],
        unique=False,
    )
    op.create_index(
        "idx_contact_request_retry_attempts_finished_at",
        "contact_request_retry_attempts",
        ["finished_at"],
        unique=False,
    )
    op.create_index(
        "idx_contact_request_retry_attempts_result_status",
        "contact_request_retry_attempts",
        ["result_status"],
        unique=False,
    )


def downgrade() -> None:
    """Drop contact request retry attempts event table."""
    op.drop_index(
        "idx_contact_request_retry_attempts_result_status",
        table_name="contact_request_retry_attempts",
    )
    op.drop_index(
        "idx_contact_request_retry_attempts_finished_at",
        table_name="contact_request_retry_attempts",
    )
    op.drop_index(
        "idx_contact_request_retry_attempts_started_at",
        table_name="contact_request_retry_attempts",
    )
    op.drop_index(
        "idx_contact_request_retry_attempts_request_id",
        table_name="contact_request_retry_attempts",
    )
    op.drop_table("contact_request_retry_attempts")
