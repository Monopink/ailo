"""Add configurable square categories and migrate category_key.

Revision ID: 20260320_02
Revises: 20260320_01
Create Date: 2026-03-20 00:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260320_02"
down_revision: str | Sequence[str] | None = "20260320_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return inspector.has_table(table_name)


def _column_exists(table_name: str, column_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def _index_exists(table_name: str, index_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(idx["name"] == index_name for idx in inspector.get_indexes(table_name))


def _foreign_key_exists(table_name: str, fk_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(fk["name"] == fk_name for fk in inspector.get_foreign_keys(table_name))


def _check_constraint_exists(table_name: str, constraint_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(
        ck["name"] == constraint_name for ck in inspector.get_check_constraints(table_name)
    )


def _unique_constraints(table_name: str) -> list[dict[str, object]]:
    if not _table_exists(table_name):
        return []
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return inspector.get_unique_constraints(table_name)


def _has_unique_constraint(table_name: str, columns: set[str]) -> bool:
    for unique in _unique_constraints(table_name):
        names = unique.get("column_names")
        if isinstance(names, list) and set(names) == columns:
            return True
    return False


def _drop_unique_constraints_by_columns(table_name: str, columns: set[str]) -> None:
    for unique in _unique_constraints(table_name):
        names = unique.get("column_names")
        constraint_name = unique.get("name")
        if (
            isinstance(names, list)
            and set(names) == columns
            and isinstance(constraint_name, str)
            and len(constraint_name) > 0
        ):
            op.drop_constraint(constraint_name, table_name, type_="unique")


def _has_any_row(sql: str) -> bool:
    bind = op.get_bind()
    return bind.execute(sa.text(sql)).scalar() is not None


def _fetch_scalars(sql: str) -> list[object]:
    bind = op.get_bind()
    return list(bind.execute(sa.text(sql)).scalars().all())


def upgrade() -> None:
    """Upgrade schema to configurable square categories."""

    if not _table_exists("square_categories"):
        op.create_table(
            "square_categories",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("category_key", sa.String(length=64), nullable=False),
            sa.Column("title", sa.String(length=50), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("theme_key", sa.String(length=20), nullable=False),
            sa.Column("icon_ref", sa.String(length=100), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("100")),
            sa.Column("status", sa.Integer(), nullable=False, server_default=sa.text("1")),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                nullable=False,
                server_default=sa.text("NOW()"),
            ),
            sa.Column(
                "updated_at",
                sa.TIMESTAMP(timezone=True),
                nullable=False,
                server_default=sa.text("NOW()"),
            ),
            sa.UniqueConstraint("category_key", name="uq_square_categories_category_key"),
            sa.CheckConstraint(
                "category_key ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$'",
                name="ck_square_categories_category_key_format",
            ),
            sa.CheckConstraint(
                "theme_key IN ('ocean', 'sky', 'mint', 'forest', 'lime', 'amber', 'sunset', 'rose', 'grape', 'slate')",
                name="ck_square_categories_theme_key",
            ),
            sa.CheckConstraint(
                "icon_ref ~ '^tdesign:[a-z0-9-]+$'",
                name="ck_square_categories_icon_ref_format",
            ),
            sa.CheckConstraint("status IN (1, 2)", name="ck_square_categories_status"),
            comment="Square category definitions for dynamic discovery tabs",
        )

    if not _index_exists("square_categories", "idx_square_categories_status_sort"):
        op.create_index(
            "idx_square_categories_status_sort",
            "square_categories",
            ["status", "sort_order", "category_key"],
            unique=False,
        )

    op.execute(
        sa.text(
            """
            INSERT INTO square_categories (category_key, title, description, theme_key, icon_ref, sort_order, status)
            VALUES
                ('friend', '交友', '结识同频的人，聊聊日常和心情', 'ocean', 'tdesign:user-filled', 10, 1),
                ('love', '恋爱', '遇见心动对象，把故事慢慢说给TA', 'rose', 'tdesign:chat-filled', 20, 1),
                ('talk', '倾诉', '想说的话有人听，情绪不必独自消化', 'amber', 'tdesign:chat', 30, 1),
                ('bestie', '闺蜜', '找个懂你的闺蜜，分享秘密与小确幸', 'grape', 'tdesign:user', 40, 1),
                ('hobby', '同好', '一起聊兴趣爱好，把话题聊到尽兴', 'forest', 'tdesign:earth', 50, 1)
            ON CONFLICT (category_key) DO NOTHING
            """
        )
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_square_category_key_update()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.category_key <> OLD.category_key THEN
                RAISE EXCEPTION 'square_categories.category_key is immutable';
            END IF;
            RETURN NEW;
        END;
        $$ language 'plpgsql';
        """
    )
    op.execute("DROP TRIGGER IF EXISTS prevent_square_category_key_update_trigger ON square_categories;")
    op.execute(
        """
        CREATE TRIGGER prevent_square_category_key_update_trigger
        BEFORE UPDATE ON square_categories
        FOR EACH ROW EXECUTE FUNCTION prevent_square_category_key_update();
        """
    )

    if _table_exists("contact_requests"):
        if not _column_exists("contact_requests", "category_key"):
            op.add_column(
                "contact_requests",
                sa.Column("category_key", sa.String(length=64), nullable=True),
            )
        if not _column_exists("contact_requests", "alias"):
            op.add_column(
                "contact_requests",
                sa.Column("alias", sa.String(length=100), nullable=True),
            )
        if not _column_exists("contact_requests", "tags"):
            op.add_column(
                "contact_requests",
                sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            )

    if not _table_exists("square_type_entries"):
        return

    if not _column_exists("square_type_entries", "category_key"):
        op.add_column(
            "square_type_entries",
            sa.Column("category_key", sa.String(length=64), nullable=True),
        )

    if _column_exists("square_type_entries", "square_category"):
        invalid_categories = _fetch_scalars(
            """
            SELECT DISTINCT square_category
            FROM square_type_entries
            WHERE square_category NOT IN (1, 2, 3, 4, 5)
            ORDER BY square_category
            """
        )
        if len(invalid_categories) > 0:
            raise RuntimeError(
                "square_type_entries.square_category contains unsupported values: "
                + ", ".join(str(item) for item in invalid_categories)
            )

        op.execute(
            sa.text(
                """
                UPDATE square_type_entries
                SET category_key = CASE square_category
                    WHEN 1 THEN 'friend'
                    WHEN 2 THEN 'love'
                    WHEN 3 THEN 'talk'
                    WHEN 4 THEN 'bestie'
                    WHEN 5 THEN 'hobby'
                    ELSE NULL
                END
                WHERE category_key IS NULL
                """
            )
        )

    if _has_any_row(
        """
        SELECT 1
        FROM square_type_entries
        WHERE category_key IS NULL
        LIMIT 1
        """
    ):
        raise RuntimeError("square_type_entries.category_key backfill failed")

    if _has_any_row(
        """
        SELECT 1
        FROM square_type_entries se
        LEFT JOIN square_categories sc ON sc.category_key = se.category_key
        WHERE sc.category_key IS NULL
        LIMIT 1
        """
    ):
        raise RuntimeError("square_type_entries.category_key contains values missing in square_categories")

    if _has_any_row(
        """
        SELECT 1
        FROM (
            SELECT type_id
            FROM square_type_entries
            WHERE status = 1
            GROUP BY type_id
            HAVING COUNT(*) > 1
        ) duplicated
        LIMIT 1
        """
    ):
        duplicated = _fetch_scalars(
            """
            SELECT type_id
            FROM square_type_entries
            WHERE status = 1
            GROUP BY type_id
            HAVING COUNT(*) > 1
            ORDER BY type_id
            LIMIT 10
            """
        )
        raise RuntimeError(
            "square_type_entries has duplicated active type_id across categories: "
            + ", ".join(str(item) for item in duplicated)
        )

    if _column_exists("square_type_entries", "square_category"):
        _drop_unique_constraints_by_columns(
            "square_type_entries", {"square_category", "type_id"}
        )
        if _index_exists("square_type_entries", "idx_square_type_entries_category"):
            op.drop_index("idx_square_type_entries_category", table_name="square_type_entries")
        op.drop_column("square_type_entries", "square_category")

    if not _check_constraint_exists("square_type_entries", "ck_square_type_entries_status"):
        op.create_check_constraint(
            "ck_square_type_entries_status",
            "square_type_entries",
            "status IN (1, 2)",
        )

    if not _has_unique_constraint("square_type_entries", {"category_key", "type_id"}):
        op.create_unique_constraint(
            "uq_square_type_entries_category_key_type_id",
            "square_type_entries",
            ["category_key", "type_id"],
        )

    op.alter_column("square_type_entries", "category_key", nullable=False)

    if not _foreign_key_exists("square_type_entries", "fk_square_type_entries_category"):
        op.create_foreign_key(
            "fk_square_type_entries_category",
            "square_type_entries",
            "square_categories",
            ["category_key"],
            ["category_key"],
            ondelete="RESTRICT",
        )

    if not _index_exists("square_type_entries", "idx_square_type_entries_category_key"):
        op.create_index(
            "idx_square_type_entries_category_key",
            "square_type_entries",
            ["category_key"],
            unique=False,
        )

    if not _index_exists("square_type_entries", "uq_square_type_entries_active_type_id"):
        op.create_index(
            "uq_square_type_entries_active_type_id",
            "square_type_entries",
            ["type_id"],
            unique=True,
            postgresql_where=sa.text("status = 1"),
        )


def downgrade() -> None:
    """Downgrade schema to numeric square_category."""

    if _table_exists("square_type_entries"):
        if not _column_exists("square_type_entries", "square_category"):
            op.add_column(
                "square_type_entries",
                sa.Column("square_category", sa.Integer(), nullable=True),
            )

        if _column_exists("square_type_entries", "category_key"):
            unknown_keys = _fetch_scalars(
                """
                SELECT DISTINCT category_key
                FROM square_type_entries
                WHERE category_key IS NOT NULL
                  AND category_key NOT IN ('friend', 'love', 'talk', 'bestie', 'hobby')
                ORDER BY category_key
                """
            )
            if len(unknown_keys) > 0:
                raise RuntimeError(
                    "square_type_entries.category_key contains keys unsupported by downgrade: "
                    + ", ".join(str(item) for item in unknown_keys)
                )

            op.execute(
                sa.text(
                    """
                    UPDATE square_type_entries
                    SET square_category = CASE category_key
                        WHEN 'friend' THEN 1
                        WHEN 'love' THEN 2
                        WHEN 'talk' THEN 3
                        WHEN 'bestie' THEN 4
                        WHEN 'hobby' THEN 5
                        ELSE NULL
                    END
                    WHERE square_category IS NULL
                    """
                )
            )

        if _has_any_row(
            """
            SELECT 1
            FROM square_type_entries
            WHERE square_category IS NULL
            LIMIT 1
            """
        ):
            raise RuntimeError("square_type_entries.square_category backfill failed during downgrade")

        if _foreign_key_exists("square_type_entries", "fk_square_type_entries_category"):
            op.drop_constraint(
                "fk_square_type_entries_category",
                "square_type_entries",
                type_="foreignkey",
            )

        if _index_exists("square_type_entries", "uq_square_type_entries_active_type_id"):
            op.drop_index(
                "uq_square_type_entries_active_type_id",
                table_name="square_type_entries",
            )

        _drop_unique_constraints_by_columns("square_type_entries", {"category_key", "type_id"})

        if _index_exists("square_type_entries", "idx_square_type_entries_category_key"):
            op.drop_index("idx_square_type_entries_category_key", table_name="square_type_entries")

        if _check_constraint_exists("square_type_entries", "ck_square_type_entries_status"):
            op.drop_constraint(
                "ck_square_type_entries_status",
                "square_type_entries",
                type_="check",
            )

        if _column_exists("square_type_entries", "category_key"):
            op.drop_column("square_type_entries", "category_key")

        if not _has_unique_constraint("square_type_entries", {"square_category", "type_id"}):
            op.create_unique_constraint(
                "square_type_entries_square_category_type_id_key",
                "square_type_entries",
                ["square_category", "type_id"],
            )

        op.alter_column("square_type_entries", "square_category", nullable=False)

        if not _index_exists("square_type_entries", "idx_square_type_entries_category"):
            op.create_index(
                "idx_square_type_entries_category",
                "square_type_entries",
                ["square_category"],
                unique=False,
            )

    if _table_exists("contact_requests"):
        if _column_exists("contact_requests", "tags"):
            op.drop_column("contact_requests", "tags")
        if _column_exists("contact_requests", "alias"):
            op.drop_column("contact_requests", "alias")
        if _column_exists("contact_requests", "category_key"):
            op.drop_column("contact_requests", "category_key")

    if _table_exists("square_categories"):
        op.execute("DROP TRIGGER IF EXISTS prevent_square_category_key_update_trigger ON square_categories;")

    op.execute("DROP FUNCTION IF EXISTS prevent_square_category_key_update();")

    if _table_exists("square_categories"):
        op.drop_table("square_categories")
