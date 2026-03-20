"""Normalize ai_instances.creation_metadata.source values.

Revision ID: 20260320_00
Revises: 20260318_01
Create Date: 2026-03-20 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260320_00"
down_revision: str | Sequence[str] | None = "20260318_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_any_row(sql: str) -> bool:
    bind = op.get_bind()
    return bind.execute(sa.text(sql)).scalar() is not None


def upgrade() -> None:
    """Normalize legacy source values to satisfy strict migration guards."""

    if _has_any_row(
        """
        SELECT 1
        FROM ai_instances
        WHERE COALESCE(creation_metadata->>'source', '') NOT IN ('persona', 'admin_manual', 'template', '')
        LIMIT 1
        """
    ):
        raise RuntimeError("ai_instances.creation_metadata.source contains unsupported value")

    if _has_any_row(
        """
        SELECT 1
        FROM ai_instances
        WHERE COALESCE(creation_metadata->>'source', '') IN ('template', '')
          AND (creation_metadata->>'persona_id') IS NULL
        LIMIT 1
        """
    ):
        raise RuntimeError("legacy template/empty source rows must include creation_metadata.persona_id")

    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE ai_instances
            SET creation_metadata = jsonb_set(
                creation_metadata,
                '{source}',
                to_jsonb('persona'::text),
                true
            )
            WHERE COALESCE(creation_metadata->>'source', '') IN ('template', '')
            """
        )
    )

    if _has_any_row(
        """
        SELECT 1
        FROM ai_instances
        WHERE COALESCE(creation_metadata->>'source', '') NOT IN ('persona', 'admin_manual')
        LIMIT 1
        """
    ):
        raise RuntimeError("ai_instances.creation_metadata.source normalization did not converge")


def downgrade() -> None:
    """Data normalization is irreversible; keep canonical values unchanged."""
