"""Add ai_instances.persona_id and drop ai_instances.username.

Revision ID: 20260320_01
Revises: 20260320_00
Create Date: 2026-03-20 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260320_01"
down_revision: str | Sequence[str] | None = "20260320_00"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def _index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(idx["name"] == index_name for idx in inspector.get_indexes(table_name))


def _foreign_key_exists(table_name: str, fk_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(fk["name"] == fk_name for fk in inspector.get_foreign_keys(table_name))


def _check_constraint_exists(table_name: str, constraint_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(
        ck["name"] == constraint_name for ck in inspector.get_check_constraints(table_name)
    )


def _has_any_row(db, sql: str) -> bool:
    return db.execute(sa.text(sql)).scalar() is not None


def upgrade() -> None:
    """Add persona_id, backfill strictly, drop username."""

    # 1) Add persona_id column (nullable)
    if not _column_exists("ai_instances", "persona_id"):
        op.add_column(
            "ai_instances",
            sa.Column("persona_id", sa.BigInteger(), nullable=True),
        )

    bind = op.get_bind()

    # 2) Strictly validate source enum (fail fast, no silent fallback)
    if _has_any_row(
        bind,
        """
        SELECT 1
        FROM ai_instances
        WHERE COALESCE(creation_metadata->>'source', '') NOT IN ('persona', 'admin_manual')
        LIMIT 1
        """,
    ):
        raise RuntimeError("ai_instances.creation_metadata.source must be 'persona' or 'admin_manual'")

    # 3) Backfill persona_id from creation_metadata.persona_id for source=persona
    bind.execute(
        sa.text(
            """
            UPDATE ai_instances
            SET persona_id = (creation_metadata->>'persona_id')::bigint
            WHERE (creation_metadata->>'source') = 'persona'
              AND persona_id IS NULL
              AND (creation_metadata->>'persona_id') IS NOT NULL
            """
        )
    )

    # 4) Strict validation
    # admin_manual must keep persona_id NULL
    if _has_any_row(
        bind,
        """
        SELECT 1
        FROM ai_instances
        WHERE (creation_metadata->>'source') = 'admin_manual'
          AND persona_id IS NOT NULL
        LIMIT 1
        """,
    ):
        raise RuntimeError("ai_instances.persona_id must be NULL for source=admin_manual")

    # persona must have persona_id in metadata
    if _has_any_row(
        bind,
        """
        SELECT 1
        FROM ai_instances
        WHERE (creation_metadata->>'source') = 'persona'
          AND (creation_metadata->>'persona_id') IS NULL
        LIMIT 1
        """,
    ):
        raise RuntimeError("ai_instances.creation_metadata.persona_id is required for source=persona")

    # persona must be backfilled to persona_id column
    if _has_any_row(
        bind,
        """
        SELECT 1
        FROM ai_instances
        WHERE (creation_metadata->>'source') = 'persona'
          AND persona_id IS NULL
        LIMIT 1
        """,
    ):
        raise RuntimeError("ai_instances.persona_id backfill failed for some source=persona rows")

    # persona_id must reference existing persona
    if _has_any_row(
        bind,
        """
        SELECT 1
        FROM ai_instances i
        LEFT JOIN ai_personas p ON p.id = i.persona_id
        WHERE i.persona_id IS NOT NULL
          AND p.id IS NULL
        LIMIT 1
        """,
    ):
        raise RuntimeError("ai_instances.persona_id references missing ai_personas row")

    # qiao_id must match persona.qiao_id for persona instances
    if _has_any_row(
        bind,
        """
        SELECT 1
        FROM ai_instances i
        JOIN ai_personas p ON p.id = i.persona_id
        WHERE (i.creation_metadata->>'source') = 'persona'
          AND i.qiao_id <> p.qiao_id
        LIMIT 1
        """,
    ):
        raise RuntimeError("ai_instances.qiao_id must match ai_personas.qiao_id for source=persona")

    # 5) Add FK and index
    if not _foreign_key_exists("ai_instances", "fk_ai_instances_persona"):
        op.create_foreign_key(
            "fk_ai_instances_persona",
            "ai_instances",
            "ai_personas",
            ["persona_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    if not _index_exists("ai_instances", "idx_ai_instances_persona_id"):
        op.create_index(
            "idx_ai_instances_persona_id",
            "ai_instances",
            ["persona_id"],
            unique=False,
            postgresql_where=sa.text("persona_id IS NOT NULL"),
        )

    # 6) Drop old username constraint/index/column
    if _check_constraint_exists("ai_instances", "ck_ai_instances_manual_username_null"):
        op.drop_constraint(
            "ck_ai_instances_manual_username_null",
            "ai_instances",
            type_="check",
        )

    if _index_exists("ai_instances", "idx_ai_instances_user_username"):
        op.drop_index("idx_ai_instances_user_username", table_name="ai_instances")

    if _column_exists("ai_instances", "username"):
        op.drop_column("ai_instances", "username")


def downgrade() -> None:
    """Re-add username and remove persona_id.

    Downgrade is best-effort and does not restore historical username snapshots.
    """

    if not _column_exists("ai_instances", "username"):
        op.add_column(
            "ai_instances",
            sa.Column("username", sa.String(length=20), nullable=True),
        )

    if not _index_exists("ai_instances", "idx_ai_instances_user_username"):
        op.create_index(
            "idx_ai_instances_user_username",
            "ai_instances",
            ["user_id", "username"],
            unique=False,
        )

    if _foreign_key_exists("ai_instances", "fk_ai_instances_persona"):
        op.drop_constraint("fk_ai_instances_persona", "ai_instances", type_="foreignkey")

    if _index_exists("ai_instances", "idx_ai_instances_persona_id"):
        op.drop_index("idx_ai_instances_persona_id", table_name="ai_instances")

    if _column_exists("ai_instances", "persona_id"):
        op.drop_column("ai_instances", "persona_id")
