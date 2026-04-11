"""Add ai_buffer_wake_events audit table.

Revision ID: 20260411_00
Revises: 20260407_01
Create Date: 2026-04-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260411_00"
down_revision: str | Sequence[str] | None = "20260407_01"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return inspector.has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def _has_constraint(table_name: str, constraint_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(c.get("name") == constraint_name for c in inspector.get_check_constraints(table_name))


def upgrade() -> None:
    if not _table_exists("ai_message_buffer"):
        return

    op.create_table(
        "ai_buffer_wake_events",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("buffer_id", sa.BigInteger(), nullable=False),
        sa.Column("user_qiao_id", sa.String(length=32), nullable=False),
        sa.Column("instance_qiao_id", sa.String(length=32), nullable=False),
        sa.Column("event_time_ms", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.String(length=32), nullable=False),
        sa.Column("trigger_message_type", sa.SmallInteger(), nullable=False),
        sa.Column("prev_wake_delay_ms", sa.Integer(), nullable=True),
        sa.Column("new_wake_delay_ms", sa.Integer(), nullable=True),
        sa.Column("micro_expires_at_ms", sa.BigInteger(), nullable=True),
        sa.Column("macro_expires_at_ms", sa.BigInteger(), nullable=True),
        sa.Column("buffer_expires_at_ms", sa.BigInteger(), nullable=True),
        sa.Column("adjustment_mode", sa.String(length=32), nullable=False),
        sa.Column("wake_time_min_ms", sa.Integer(), nullable=False),
        sa.Column("wake_time_max_ms", sa.Integer(), nullable=False),
        sa.Column("wake_time_bias", sa.String(length=32), nullable=False),
        sa.Column("random_number", sa.Integer(), nullable=True),
        sa.Column("wake_adjustment_count_after", sa.SmallInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ai_buffer_wake_events"),
    )
    op.create_index(
        "idx_ai_buffer_wake_events_buffer_time",
        "ai_buffer_wake_events",
        ["buffer_id", "created_at"],
    )

    if _has_column("ai_message_buffer", "wake_expires_at_ms"):
        op.add_column(
            "ai_message_buffer",
            sa.Column(
                "wake_delay_ms",
                sa.Integer(),
                nullable=True,
                comment="Wake delay (ms) applied after timer_due_ms; NULL when wake gate is inactive",
            ),
        )

        op.execute(
            sa.text(
                """
                UPDATE ai_message_buffer
                SET wake_delay_ms = GREATEST(wake_expires_at_ms - (EXTRACT(EPOCH FROM NOW())*1000)::BIGINT, 0)::INT
                WHERE wake_expires_at_ms IS NOT NULL
                """
            )
        )

        if _has_constraint("ai_message_buffer", "ck_wake_expires_state"):
            op.drop_constraint("ck_wake_expires_state", "ai_message_buffer", type_="check")
        op.drop_column("ai_message_buffer", "wake_expires_at_ms")

        op.create_check_constraint(
            "ck_wake_delay_state",
            "ai_message_buffer",
            "(aggregate_state = 0 AND wake_delay_ms IS NOT NULL) OR (aggregate_state <> 0 AND wake_delay_ms IS NULL)",
        )


def downgrade() -> None:
    if _table_exists("ai_buffer_wake_events"):
        op.drop_index("idx_ai_buffer_wake_events_buffer_time", table_name="ai_buffer_wake_events")
        op.drop_table("ai_buffer_wake_events")

    if _table_exists("ai_message_buffer"):
        if _has_constraint("ai_message_buffer", "ck_wake_delay_state"):
            op.drop_constraint("ck_wake_delay_state", "ai_message_buffer", type_="check")
        if _has_column("ai_message_buffer", "wake_delay_ms"):
            op.add_column(
                "ai_message_buffer",
                sa.Column(
                    "wake_expires_at_ms",
                    sa.BigInteger(),
                    nullable=True,
                    comment="Wake gate deadline (ms), NULL when wake gate is inactive",
                ),
            )
            op.execute(
                sa.text(
                    """
                    UPDATE ai_message_buffer
                    SET wake_expires_at_ms = (EXTRACT(EPOCH FROM NOW())*1000)::BIGINT + wake_delay_ms
                    WHERE wake_delay_ms IS NOT NULL
                    """
                )
            )
            op.drop_column("ai_message_buffer", "wake_delay_ms")

        op.create_check_constraint(
            "ck_wake_expires_state",
            "ai_message_buffer",
            "(aggregate_state = 0 AND wake_expires_at_ms IS NOT NULL) OR (aggregate_state <> 0 AND wake_expires_at_ms IS NULL)",
        )
