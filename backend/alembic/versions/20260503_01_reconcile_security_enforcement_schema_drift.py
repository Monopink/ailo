"""Reconcile security enforcement schema drift caused by revision-id reuse.

Revision ID: 20260503_01
Revises: 20260502_04
Create Date: 2026-05-03 14:10:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260503_01"
down_revision: str | Sequence[str] | None = "20260502_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Reconcile missing security-enforcement schema objects on drifted databases."""
    op.execute(
        """
        ALTER TABLE user_violation_logs
        ALTER COLUMN user_id DROP NOT NULL,
        ALTER COLUMN user_qiao_id DROP NOT NULL,
        ALTER COLUMN user_id DROP DEFAULT,
        ALTER COLUMN user_qiao_id DROP DEFAULT,
        ADD COLUMN IF NOT EXISTS rule_code VARCHAR(64),
        ADD COLUMN IF NOT EXISTS rule_version VARCHAR(32),
        ADD COLUMN IF NOT EXISTS detection_source INTEGER,
        ADD COLUMN IF NOT EXISTS http_method VARCHAR(16),
        ADD COLUMN IF NOT EXISTS request_path VARCHAR(255),
        ADD COLUMN IF NOT EXISTS client_ip INET,
        ADD COLUMN IF NOT EXISTS request_id VARCHAR(64),
        ADD COLUMN IF NOT EXISTS evidence_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
        ADD COLUMN IF NOT EXISTS trigger_score INTEGER
        """
    )

    op.execute(
        """
        ALTER TABLE user_risk_stats
        ADD COLUMN IF NOT EXISTS high_risk_hits INTEGER NOT NULL DEFAULT 0,
        ADD COLUMN IF NOT EXISTS last_high_risk_at TIMESTAMPTZ,
        ADD COLUMN IF NOT EXISTS last_suspend_at TIMESTAMPTZ
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS security_ip_risk_stats (
            id BIGINT PRIMARY KEY,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            ip_address INET NOT NULL,
            high_risk_count_5m INTEGER NOT NULL DEFAULT 0,
            medium_risk_count_10m INTEGER NOT NULL DEFAULT 0,
            total_attack_count INTEGER NOT NULL DEFAULT 0,
            last_attack_at TIMESTAMPTZ NULL,
            last_rule_code VARCHAR(64) NULL,
            last_source VARCHAR(32) NULL,
            last_request_path VARCHAR(255) NULL,
            last_user_id BIGINT NULL,
            CONSTRAINT ck_security_ip_risk_stats_high_5m_nonneg CHECK (high_risk_count_5m >= 0),
            CONSTRAINT ck_security_ip_risk_stats_medium_10m_nonneg
                CHECK (medium_risk_count_10m >= 0),
            CONSTRAINT ck_security_ip_risk_stats_total_nonneg CHECK (total_attack_count >= 0)
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_security_ip_risk_stats_ip
        ON security_ip_risk_stats (ip_address)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_security_ip_risk_stats_last_attack
        ON security_ip_risk_stats (last_attack_at)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS security_ip_blocks (
            id BIGINT PRIMARY KEY,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            ip_address INET NOT NULL,
            block_scope SMALLINT NOT NULL DEFAULT 1,
            cidr_prefix SMALLINT NULL,
            severity_level SMALLINT NOT NULL,
            reason_code VARCHAR(64) NOT NULL,
            rule_code VARCHAR(64) NOT NULL,
            rule_version VARCHAR(32) NOT NULL,
            source VARCHAR(32) NOT NULL,
            request_path VARCHAR(255) NULL,
            request_method VARCHAR(16) NULL,
            evidence_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
            hit_count INTEGER NOT NULL DEFAULT 1,
            first_hit_at TIMESTAMPTZ NOT NULL,
            blocked_at TIMESTAMPTZ NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL,
            status SMALLINT NOT NULL DEFAULT 1,
            released_at TIMESTAMPTZ NULL,
            release_reason VARCHAR(128) NULL,
            CONSTRAINT ck_security_ip_blocks_expiry_after_blocked CHECK (expires_at > blocked_at),
            CONSTRAINT ck_security_ip_blocks_status CHECK (status IN (1, 2, 3)),
            CONSTRAINT ck_security_ip_blocks_scope CHECK (block_scope IN (1, 2)),
            CONSTRAINT ck_security_ip_blocks_severity CHECK (severity_level IN (1, 2, 3, 4)),
            CONSTRAINT ck_security_ip_blocks_scope_prefix CHECK (
                (block_scope = 1 AND cidr_prefix IS NULL)
                OR (block_scope = 2 AND cidr_prefix IS NOT NULL AND cidr_prefix BETWEEN 0 AND 128)
            ),
            CONSTRAINT ck_security_ip_blocks_hit_count_pos CHECK (hit_count >= 1)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_security_ip_blocks_ip_status_expire
        ON security_ip_blocks (ip_address, status, expires_at)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_security_ip_blocks_expire
        ON security_ip_blocks (expires_at)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_security_ip_blocks_rule_time
        ON security_ip_blocks (rule_code, blocked_at)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_security_ip_blocks_source_time
        ON security_ip_blocks (source, blocked_at)
        """
    )

    op.execute(
        """
        INSERT INTO system_configs (
            config_key,
            config_value,
            default_value,
            value_type,
            config_shape,
            description,
            group_name,
            config_scope,
            allowed_values
        ) VALUES
            (
                'security_user_auto_suspend_enabled',
                'true'::jsonb,
                'true'::jsonb,
                3,
                1,
                'Enable automatic user suspension on high-risk attacks',
                'security_attack',
                'security',
                NULL
            ),
            (
                'security_rule_version',
                '"2026-05-02"'::jsonb,
                '"2026-05-02"'::jsonb,
                1,
                1,
                'Current attack-rule version used by enforcement pipeline',
                'security_attack',
                'security',
                NULL
            ),
            (
                'security_ip_block_high_ttl_seconds',
                '86400'::jsonb,
                '86400'::jsonb,
                2,
                1,
                'TTL (seconds) for high-risk IP block when threshold reached',
                'security_attack',
                'security',
                NULL
            ),
            (
                'security_ip_block_medium_ttl_seconds',
                '3600'::jsonb,
                '3600'::jsonb,
                2,
                1,
                'TTL (seconds) for medium-risk IP block when threshold reached',
                'security_attack',
                'security',
                NULL
            ),
            (
                'security_ip_high_risk_threshold_count',
                '8'::jsonb,
                '8'::jsonb,
                2,
                1,
                'High-risk IP hit count threshold',
                'security_attack',
                'security',
                NULL
            ),
            (
                'security_ip_high_risk_threshold_window_seconds',
                '300'::jsonb,
                '300'::jsonb,
                2,
                1,
                'High-risk IP threshold window in seconds',
                'security_attack',
                'security',
                NULL
            ),
            (
                'security_ip_medium_risk_threshold_count',
                '20'::jsonb,
                '20'::jsonb,
                2,
                1,
                'Medium-risk IP hit count threshold',
                'security_attack',
                'security',
                NULL
            ),
            (
                'security_ip_medium_risk_threshold_window_seconds',
                '600'::jsonb,
                '600'::jsonb,
                2,
                1,
                'Medium-risk IP threshold window in seconds',
                'security_attack',
                'security',
                NULL
            )
        ON CONFLICT (config_key) DO NOTHING
        """
    )


def downgrade() -> None:
    """Reconciliation migration is intentionally non-destructive."""
