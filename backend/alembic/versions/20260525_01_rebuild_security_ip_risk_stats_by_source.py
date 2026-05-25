"""Rebuild security_ip_risk_stats with source dimension.

Revision ID: 20260525_01
Revises: 20260524_01
Create Date: 2026-05-25 22:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260525_01"
down_revision: str | Sequence[str] | None = "20260524_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_security_ip_risk_stats_v2() -> None:
    op.execute(
        """
        CREATE TABLE security_ip_risk_stats (
            id BIGINT PRIMARY KEY,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            ip_address INET NOT NULL,
            detection_source INTEGER NOT NULL,
            high_risk_count_5m INTEGER NOT NULL DEFAULT 0,
            medium_risk_count_10m INTEGER NOT NULL DEFAULT 0,
            total_attack_count INTEGER NOT NULL DEFAULT 0,
            last_attack_at TIMESTAMPTZ NULL,
            last_rule_code VARCHAR(64) NULL,
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
        CREATE UNIQUE INDEX uq_security_ip_risk_stats_ip_source
        ON security_ip_risk_stats (ip_address, detection_source)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_security_ip_risk_stats_last_attack
        ON security_ip_risk_stats (last_attack_at)
        """
    )


def _create_security_ip_risk_stats_v1() -> None:
    op.execute(
        """
        CREATE TABLE security_ip_risk_stats (
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
        CREATE UNIQUE INDEX uq_security_ip_risk_stats_ip
        ON security_ip_risk_stats (ip_address)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_security_ip_risk_stats_last_attack
        ON security_ip_risk_stats (last_attack_at)
        """
    )


def upgrade() -> None:
    """Rebuild security_ip_risk_stats to isolate counters by detection source."""
    op.execute("DROP TABLE IF EXISTS security_ip_risk_stats")
    _create_security_ip_risk_stats_v2()


def downgrade() -> None:
    """Restore previous single-row-per-IP shape for security_ip_risk_stats."""
    op.execute("DROP TABLE IF EXISTS security_ip_risk_stats")
    _create_security_ip_risk_stats_v1()
