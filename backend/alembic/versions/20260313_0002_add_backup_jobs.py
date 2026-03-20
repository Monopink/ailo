"""Add backup_jobs table.

Revision ID: 20260313_0002
Revises: 20260311_0001
Create Date: 2026-03-13 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260313_0002"
down_revision: str | Sequence[str] | None = "20260311_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "backup_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("status", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.BigInteger(), nullable=True),
        sa.Column("backup_file_name", sa.String(length=255), nullable=True),
        sa.Column("object_key", sa.Text(), nullable=True),
        sa.Column("bucket_name", sa.String(length=255), nullable=True),
        sa.Column("storage_region", sa.String(length=64), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("etag", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint("status IN (1, 2, 3)", name="ck_backup_jobs_status"),
    )

    op.create_index("idx_backup_jobs_started_at", "backup_jobs", ["started_at"])
    op.create_index("idx_backup_jobs_status", "backup_jobs", ["status"])
    op.create_index("idx_backup_jobs_created_at", "backup_jobs", ["created_at"])

    op.execute(
        """
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
""".strip()
    )
    op.execute("DROP TRIGGER IF EXISTS update_backup_jobs_updated_at ON backup_jobs;")
    op.execute(
        "CREATE TRIGGER update_backup_jobs_updated_at "
        "BEFORE UPDATE ON backup_jobs FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TRIGGER IF EXISTS update_backup_jobs_updated_at ON backup_jobs;")
    op.drop_index("idx_backup_jobs_created_at", table_name="backup_jobs")
    op.drop_index("idx_backup_jobs_status", table_name="backup_jobs")
    op.drop_index("idx_backup_jobs_started_at", table_name="backup_jobs")
    op.drop_table("backup_jobs")
