"""Refactor AI instance memories for policy-based dedup and forgetting.

Revision ID: 20260507_01
Revises: 20260506_02
Create Date: 2026-05-07 16:40:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260507_01"
down_revision: str | Sequence[str] | None = "20260506_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add policy fields and indexes for AI instance memories."""
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.add_column(
        "ai_instance_memories",
        sa.Column(
            "normalized_content",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
            comment="Normalized content used for deduplication",
        ),
    )
    op.add_column(
        "ai_instance_memories",
        sa.Column(
            "reinforce_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment="Reinforcement count for merged/recalled memories",
        ),
    )
    op.add_column(
        "ai_instance_memories",
        sa.Column(
            "last_reinforced_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Last reinforcement timestamp",
        ),
    )
    op.add_column(
        "ai_instance_memories",
        sa.Column(
            "source_strength",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
            comment="Source strength rank (1-5)",
        ),
    )
    op.add_column(
        "ai_instance_memories",
        sa.Column(
            "fact_key",
            sa.String(length=128),
            nullable=True,
            comment="Rule-based fact key for conservative conflict handling",
        ),
    )
    op.add_column(
        "ai_instance_memories",
        sa.Column(
            "conflict_flag",
            sa.Integer(),
            nullable=True,
            comment="Conflict resolution marker",
        ),
    )

    op.execute(
        """
        UPDATE ai_instance_memories
        SET normalized_content = regexp_replace(btrim(content), '\\s+', ' ', 'g')
        WHERE normalized_content = ''
        """
    )
    op.execute(
        """
        UPDATE ai_instance_memories
        SET source_strength = CASE
            WHEN source_message_id IS NOT NULL THEN 2
            ELSE 1
        END
        """
    )
    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY instance_id, normalized_content
                    ORDER BY updated_at DESC, id DESC
                ) AS rn
            FROM ai_instance_memories
            WHERE status = 1
        )
        UPDATE ai_instance_memories m
        SET status = 2, updated_at = NOW()
        FROM ranked r
        WHERE m.id = r.id
          AND r.rn > 1
        """
    )

    op.create_check_constraint(
        "ck_instance_memories_source_strength_range",
        "ai_instance_memories",
        "source_strength BETWEEN 1 AND 5",
    )

    op.drop_index("uq_ai_instance_memories_content", table_name="ai_instance_memories")

    op.create_index(
        "idx_ai_instance_memories_fact_key_active",
        "ai_instance_memories",
        ["instance_id", "fact_key"],
        unique=False,
        postgresql_where=sa.text("status = 1 AND fact_key IS NOT NULL"),
    )
    op.create_index(
        "idx_ai_instance_memories_norm_active",
        "ai_instance_memories",
        ["instance_id", "normalized_content"],
        unique=False,
        postgresql_where=sa.text("status = 1"),
    )
    op.create_index(
        "idx_ai_instance_memories_norm_trgm",
        "ai_instance_memories",
        ["normalized_content"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"normalized_content": "gin_trgm_ops"},
    )
    op.create_index(
        "uq_ai_instance_memory_active_norm",
        "ai_instance_memories",
        ["instance_id", "normalized_content"],
        unique=True,
        postgresql_where=sa.text("status = 1"),
    )


def downgrade() -> None:
    """Rollback AI instance memories policy field changes."""
    op.drop_index("uq_ai_instance_memory_active_norm", table_name="ai_instance_memories")
    op.drop_index("idx_ai_instance_memories_norm_trgm", table_name="ai_instance_memories")
    op.drop_index("idx_ai_instance_memories_norm_active", table_name="ai_instance_memories")
    op.drop_index("idx_ai_instance_memories_fact_key_active", table_name="ai_instance_memories")

    op.create_index(
        "uq_ai_instance_memories_content",
        "ai_instance_memories",
        ["instance_id", "content"],
        unique=True,
    )

    op.drop_constraint(
        "ck_instance_memories_source_strength_range",
        "ai_instance_memories",
        type_="check",
    )

    op.drop_column("ai_instance_memories", "conflict_flag")
    op.drop_column("ai_instance_memories", "fact_key")
    op.drop_column("ai_instance_memories", "source_strength")
    op.drop_column("ai_instance_memories", "last_reinforced_at")
    op.drop_column("ai_instance_memories", "reinforce_count")
    op.drop_column("ai_instance_memories", "normalized_content")
