"""Add global-unique marker and uniqueness constraints for personality placeholders.

Revision ID: 20260524_01
Revises: 20260522_03
Create Date: 2026-05-24 16:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260524_01"
down_revision: str | Sequence[str] | None = "20260522_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add placeholder global-unique flag and template prompt_variables GIN index."""
    bind = op.get_bind()
    duplicate_rows = bind.execute(
        sa.text(
            """
            SELECT personality_id, placeholder_key, COUNT(*) AS duplicate_count
            FROM ai_personality_placeholders
            GROUP BY personality_id, placeholder_key
            HAVING COUNT(*) > 1
            ORDER BY duplicate_count DESC, personality_id, placeholder_key
            LIMIT 5
            """
        )
    ).fetchall()
    if duplicate_rows:
        examples = ", ".join(
            f"(personality_id={row.personality_id}, key={row.placeholder_key}, count={row.duplicate_count})"
            for row in duplicate_rows
        )
        raise RuntimeError(
            "Cannot add uq_ai_personality_placeholders_personality_key due to existing duplicates: "
            f"{examples}"
        )

    op.add_column(
        "ai_personality_placeholders",
        sa.Column(
            "is_global_unique",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Whether this placeholder key requires global unique value across templates",
        ),
    )
    op.create_unique_constraint(
        "uq_ai_personality_placeholders_personality_key",
        "ai_personality_placeholders",
        ["personality_id", "placeholder_key"],
    )
    op.create_index(
        "idx_ai_templates_prompt_variables_gin",
        "ai_templates",
        ["prompt_variables"],
        unique=False,
        postgresql_using="gin",
        postgresql_where=sa.text("prompt_variables IS NOT NULL"),
    )


def downgrade() -> None:
    """Drop placeholder global-unique flag and template prompt_variables GIN index."""
    op.drop_index("idx_ai_templates_prompt_variables_gin", table_name="ai_templates")
    op.drop_constraint(
        "uq_ai_personality_placeholders_personality_key",
        "ai_personality_placeholders",
        type_="unique",
    )
    op.drop_column("ai_personality_placeholders", "is_global_unique")
