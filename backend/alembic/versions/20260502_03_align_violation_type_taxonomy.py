"""Align security taxonomy and add attack enforcement schema.

Revision ID: 20260502_03
Revises: 20260502_02
Create Date: 2026-05-02 22:10:00
"""

# ruff: noqa: E501

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260502_03"
down_revision: str | Sequence[str] | None = "20260502_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Map historical violation types and extend enforcement schema."""
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
            CONSTRAINT ck_security_ip_risk_stats_medium_10m_nonneg CHECK (medium_risk_count_10m >= 0),
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
        UPDATE user_violation_logs
        SET violation_type = CASE violation_type
            WHEN 2 THEN 99
            WHEN 3 THEN 99
            WHEN 4 THEN 99
            WHEN 5 THEN 99
            WHEN 6 THEN 2
            WHEN 7 THEN 3
            WHEN 8 THEN 4
            WHEN 9 THEN 99
            ELSE violation_type
        END
        WHERE violation_type IN (2, 3, 4, 5, 6, 7, 8, 9)
        """
    )

    op.execute(
        """
        UPDATE user_risk_stats AS urs
        SET violation_by_type = merged.result_payload
        FROM (
            SELECT
                s.id,
                (
                    COALESCE(s.unknown_payload, '{}'::jsonb)
                    || jsonb_strip_nulls(
                        jsonb_build_object(
                            'prompt_injection', CASE WHEN s.prompt_injection_count > 0 THEN s.prompt_injection_count ELSE NULL END,
                            'sql_injection', CASE WHEN s.sql_injection_count > 0 THEN s.sql_injection_count ELSE NULL END,
                            'command_injection', CASE WHEN s.command_injection_count > 0 THEN s.command_injection_count ELSE NULL END,
                            'path_traversal', CASE WHEN s.path_traversal_count > 0 THEN s.path_traversal_count ELSE NULL END,
                            'other', CASE WHEN s.other_count > 0 THEN s.other_count ELSE NULL END
                        )
                    )
                ) AS result_payload
            FROM (
                SELECT
                    urs_inner.id,
                    CASE
                        WHEN COALESCE(urs_inner.violation_by_type->>'prompt_injection', '') ~ '^\\d+$'
                            THEN (urs_inner.violation_by_type->>'prompt_injection')::integer
                        ELSE 0
                    END AS prompt_injection_count,
                    CASE
                        WHEN COALESCE(urs_inner.violation_by_type->>'sql_injection', '') ~ '^\\d+$'
                            THEN (urs_inner.violation_by_type->>'sql_injection')::integer
                        ELSE 0
                    END AS sql_injection_count,
                    CASE
                        WHEN COALESCE(urs_inner.violation_by_type->>'command_injection', '') ~ '^\\d+$'
                            THEN (urs_inner.violation_by_type->>'command_injection')::integer
                        ELSE 0
                    END AS command_injection_count,
                    CASE
                        WHEN COALESCE(urs_inner.violation_by_type->>'path_traversal', '') ~ '^\\d+$'
                            THEN (urs_inner.violation_by_type->>'path_traversal')::integer
                        ELSE 0
                    END AS path_traversal_count,
                    (
                        CASE
                            WHEN COALESCE(urs_inner.violation_by_type->>'other', '') ~ '^\\d+$'
                                THEN (urs_inner.violation_by_type->>'other')::integer
                            ELSE 0
                        END
                        + CASE
                            WHEN COALESCE(urs_inner.violation_by_type->>'abuse_content', '') ~ '^\\d+$'
                                THEN (urs_inner.violation_by_type->>'abuse_content')::integer
                            ELSE 0
                        END
                        + CASE
                            WHEN COALESCE(urs_inner.violation_by_type->>'spam', '') ~ '^\\d+$'
                                THEN (urs_inner.violation_by_type->>'spam')::integer
                            ELSE 0
                        END
                        + CASE
                            WHEN COALESCE(urs_inner.violation_by_type->>'harassment', '') ~ '^\\d+$'
                                THEN (urs_inner.violation_by_type->>'harassment')::integer
                            ELSE 0
                        END
                    ) AS other_count,
                    (
                        SELECT jsonb_object_agg(e.key, e.value)
                        FROM jsonb_each(urs_inner.violation_by_type) AS e(key, value)
                        WHERE e.key NOT IN (
                            'prompt_injection',
                            'sql_injection',
                            'command_injection',
                            'path_traversal',
                            'other',
                            'abuse_content',
                            'spam',
                            'harassment'
                        )
                    ) AS unknown_payload
                FROM user_risk_stats AS urs_inner
            ) AS s
        ) AS merged
        WHERE urs.id = merged.id
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
                '\"2026-05-02\"'::jsonb,
                '\"2026-05-02\"'::jsonb,
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
    """Best-effort rollback for violation_type values.

    Note: the upgrade merges legacy categories into `other`, so downgrade cannot
    recover the original split between abuse/spam/harassment.
    """
    op.execute(
        """
        DELETE FROM system_configs
        WHERE config_key IN (
            'security_user_auto_suspend_enabled',
            'security_rule_version',
            'security_ip_block_high_ttl_seconds',
            'security_ip_block_medium_ttl_seconds',
            'security_ip_high_risk_threshold_count',
            'security_ip_high_risk_threshold_window_seconds',
            'security_ip_medium_risk_threshold_count',
            'security_ip_medium_risk_threshold_window_seconds'
        )
        """
    )

    op.execute(
        """
        DROP INDEX IF EXISTS idx_security_ip_blocks_source_time
        """
    )
    op.execute(
        """
        DROP INDEX IF EXISTS idx_security_ip_blocks_rule_time
        """
    )
    op.execute(
        """
        DROP INDEX IF EXISTS idx_security_ip_blocks_expire
        """
    )
    op.execute(
        """
        DROP INDEX IF EXISTS idx_security_ip_blocks_ip_status_expire
        """
    )
    op.execute(
        """
        DROP TABLE IF EXISTS security_ip_blocks
        """
    )
    op.execute(
        """
        DROP INDEX IF EXISTS idx_security_ip_risk_stats_last_attack
        """
    )
    op.execute(
        """
        DROP INDEX IF EXISTS uq_security_ip_risk_stats_ip
        """
    )
    op.execute(
        """
        DROP TABLE IF EXISTS security_ip_risk_stats
        """
    )

    op.execute(
        """
        ALTER TABLE user_risk_stats
        DROP COLUMN IF EXISTS high_risk_hits,
        DROP COLUMN IF EXISTS last_high_risk_at,
        DROP COLUMN IF EXISTS last_suspend_at
        """
    )

    op.execute(
        """
        DELETE FROM user_violation_logs
        WHERE user_id IS NULL OR user_qiao_id IS NULL
        """
    )

    op.execute(
        """
        ALTER TABLE user_violation_logs
        ALTER COLUMN user_id SET NOT NULL,
        ALTER COLUMN user_qiao_id SET NOT NULL,
        DROP COLUMN IF EXISTS rule_code,
        DROP COLUMN IF EXISTS rule_version,
        DROP COLUMN IF EXISTS detection_source,
        DROP COLUMN IF EXISTS http_method,
        DROP COLUMN IF EXISTS request_path,
        DROP COLUMN IF EXISTS client_ip,
        DROP COLUMN IF EXISTS request_id,
        DROP COLUMN IF EXISTS evidence_payload,
        DROP COLUMN IF EXISTS trigger_score
        """
    )

    op.execute(
        """
        UPDATE user_violation_logs
        SET violation_type = CASE violation_type
            WHEN 2 THEN 6
            WHEN 3 THEN 7
            WHEN 4 THEN 8
            WHEN 5 THEN 9
            WHEN 99 THEN 5
            ELSE violation_type
        END
        WHERE violation_type IN (2, 3, 4, 5, 99)
        """
    )
