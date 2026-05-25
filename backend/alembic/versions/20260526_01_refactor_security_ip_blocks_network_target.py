"""Refactor security_ip_blocks to network target storage.

Revision ID: 20260526_01
Revises: 20260525_01
Create Date: 2026-05-26 01:15:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260526_01"
down_revision: str | Sequence[str] | None = "20260525_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Replace ip+scope+prefix representation with a single CIDR target."""
    op.execute(
        """
        ALTER TABLE security_ip_blocks
        ADD COLUMN IF NOT EXISTS target_network CIDR
        """
    )
    op.execute(
        """
        UPDATE security_ip_blocks
        SET target_network = CASE
            WHEN block_scope = 2 AND cidr_prefix IS NOT NULL
                THEN set_masklen(ip_address, cidr_prefix)::cidr
            ELSE set_masklen(
                ip_address,
                CASE WHEN family(ip_address) = 4 THEN 32 ELSE 128 END
            )::cidr
        END
        """
    )
    op.execute(
        """
        ALTER TABLE security_ip_blocks
        ALTER COLUMN target_network SET NOT NULL
        """
    )
    op.execute("DROP INDEX IF EXISTS idx_security_ip_blocks_ip_status_expire")
    op.execute("DROP INDEX IF EXISTS idx_security_ip_blocks_status_expire")
    op.execute("DROP INDEX IF EXISTS idx_security_ip_blocks_target_network_gist")
    op.execute(
        """
        ALTER TABLE security_ip_blocks
        DROP CONSTRAINT IF EXISTS ck_security_ip_blocks_scope
        """
    )
    op.execute(
        """
        ALTER TABLE security_ip_blocks
        DROP CONSTRAINT IF EXISTS ck_security_ip_blocks_scope_prefix
        """
    )
    op.execute(
        """
        ALTER TABLE security_ip_blocks
        DROP COLUMN IF EXISTS block_scope,
        DROP COLUMN IF EXISTS cidr_prefix,
        DROP COLUMN IF EXISTS ip_address
        """
    )
    op.execute(
        """
        CREATE INDEX idx_security_ip_blocks_target_network_gist
        ON security_ip_blocks
        USING gist (target_network inet_ops)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_security_ip_blocks_status_expire
        ON security_ip_blocks (status, expires_at)
        """
    )


def downgrade() -> None:
    """Restore legacy ip+scope+prefix representation."""
    op.execute(
        """
        ALTER TABLE security_ip_blocks
        ADD COLUMN IF NOT EXISTS ip_address INET,
        ADD COLUMN IF NOT EXISTS block_scope SMALLINT NOT NULL DEFAULT 1,
        ADD COLUMN IF NOT EXISTS cidr_prefix SMALLINT
        """
    )
    op.execute(
        """
        UPDATE security_ip_blocks
        SET
            ip_address = network(target_network)::inet,
            block_scope = CASE
                WHEN masklen(target_network) = CASE WHEN family(target_network) = 4 THEN 32 ELSE 128 END
                    THEN 1
                ELSE 2
            END,
            cidr_prefix = CASE
                WHEN masklen(target_network) = CASE WHEN family(target_network) = 4 THEN 32 ELSE 128 END
                    THEN NULL
                ELSE masklen(target_network)
            END
        """
    )
    op.execute(
        """
        ALTER TABLE security_ip_blocks
        ALTER COLUMN ip_address SET NOT NULL
        """
    )
    op.execute("DROP INDEX IF EXISTS idx_security_ip_blocks_target_network_gist")
    op.execute("DROP INDEX IF EXISTS idx_security_ip_blocks_status_expire")
    op.execute(
        """
        ALTER TABLE security_ip_blocks
        DROP COLUMN IF EXISTS target_network
        """
    )
    op.execute(
        """
        ALTER TABLE security_ip_blocks
        ADD CONSTRAINT ck_security_ip_blocks_scope
        CHECK (block_scope IN (1, 2))
        """
    )
    op.execute(
        """
        ALTER TABLE security_ip_blocks
        ADD CONSTRAINT ck_security_ip_blocks_scope_prefix
        CHECK (
            (block_scope = 1 AND cidr_prefix IS NULL)
            OR (block_scope = 2 AND cidr_prefix IS NOT NULL AND cidr_prefix BETWEEN 0 AND 128)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX idx_security_ip_blocks_ip_status_expire
        ON security_ip_blocks (ip_address, status, expires_at)
        """
    )
