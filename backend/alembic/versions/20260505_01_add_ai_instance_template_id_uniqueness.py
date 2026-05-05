"""Add structured template_id to ai_instances and enforce per-user template uniqueness.

Revision ID: 20260505_01
Revises: 20260504_01
Create Date: 2026-05-05 18:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260505_01"
down_revision: str | Sequence[str] | None = "20260504_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add ai_instances.template_id with backfill, FK, and uniqueness index."""
    op.add_column(
        "ai_instances",
        sa.Column(
            "template_id",
            sa.Integer(),
            nullable=True,
            comment="Selected ai_templates.id for source=persona; NULL for admin_manual instances",
        ),
    )

    op.execute(
        """
        UPDATE ai_instances
        SET template_id = CASE
            WHEN jsonb_typeof(creation_metadata -> 'template_id') = 'number'
                THEN (creation_metadata ->> 'template_id')::integer
            WHEN jsonb_typeof(creation_metadata -> 'template_id') = 'string'
                AND (creation_metadata ->> 'template_id') ~ '^[0-9]+$'
                THEN (creation_metadata ->> 'template_id')::integer
            ELSE NULL
        END
        WHERE template_id IS NULL
          AND creation_metadata ? 'template_id'
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM ai_instances
                WHERE template_id IS NOT NULL
                GROUP BY user_id, template_id
                HAVING COUNT(*) > 1
            ) THEN
                RAISE EXCEPTION 'Duplicate ai_instances rows exist for (user_id, template_id)';
            END IF;
        END
        $$;
        """
    )

    op.create_foreign_key(
        "fk_ai_instances_template",
        "ai_instances",
        "ai_templates",
        ["template_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "idx_ai_instances_template_id",
        "ai_instances",
        ["template_id"],
        unique=False,
        postgresql_where=sa.text("template_id IS NOT NULL"),
    )
    op.create_index(
        "uq_ai_instances_user_template",
        "ai_instances",
        ["user_id", "template_id"],
        unique=True,
        postgresql_where=sa.text("template_id IS NOT NULL"),
    )


def downgrade() -> None:
    """Remove template_id structure and uniqueness constraint from ai_instances."""
    op.drop_index("uq_ai_instances_user_template", table_name="ai_instances")
    op.drop_index("idx_ai_instances_template_id", table_name="ai_instances")
    op.drop_constraint("fk_ai_instances_template", "ai_instances", type_="foreignkey")
    op.drop_column("ai_instances", "template_id")
