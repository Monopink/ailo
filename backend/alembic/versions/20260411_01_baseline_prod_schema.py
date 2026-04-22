"""Baseline revision for production schema before invitation rollout.

Revision ID: 20260411_01
Revises: None
Create Date: 2026-04-15 16:05:00
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260411_01"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BASELINE_SQL_FILE = "20260411_01_baseline_prod_schema.sql"


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return inspector.has_table(table_name)


def _load_baseline_sql() -> str:
    sql_path = Path(__file__).with_name(_BASELINE_SQL_FILE)
    sql_text = sql_path.read_text(encoding="utf-8")
    # pg_dump outputs psql meta commands (\restrict/\unrestrict) that
    # are not executable via DBAPI cursor.execute.
    lines = [
        line
        for line in sql_text.splitlines()
        if not line.startswith("\\") and "set_config('search_path', '', false)" not in line.lower()
    ]
    return "\n".join(lines).strip() + "\n"


def upgrade() -> None:
    """Create baseline schema for empty databases.

    Existing databases should be stamped to this revision and skip execution.
    """
    if _table_exists("users"):
        return
    op.get_bind().exec_driver_sql(_load_baseline_sql())


def downgrade() -> None:
    """Baseline downgrade is intentionally unsupported."""
