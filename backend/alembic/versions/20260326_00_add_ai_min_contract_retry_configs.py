"""
Revision ID: 20260326_00
Revises: 20260323_00
Create Date: 2026-03-26 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260326_00"
down_revision: str | Sequence[str] | None = "20260323_00"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return inspector.has_table(table_name)


def upgrade() -> None:
    """Insert minimal-contract retry configs into system_configs."""
    if not _table_exists("system_configs"):
        return

    op.execute(
        sa.text(
            """
            INSERT INTO system_configs (
                config_key,
                config_value,
                default_value,
                config_type,
                description,
                group_name,
                allowed_values
            ) VALUES
            (
                'ai_llm_min_contract_retry_enabled',
                'true',
                'true',
                3,
                'Enable minimal-contract retry for AI LLM responses',
                'ai_conversation',
                NULL
            ),
            (
                'ai_llm_min_contract_retry_max_attempts',
                '3',
                '3',
                2,
                'Maximum attempts for minimal-contract retry (>=1)',
                'ai_conversation',
                NULL
            ),
            (
                'ai_llm_min_contract_retry_backoff_ms',
                '300',
                '300',
                2,
                'Fixed backoff interval in milliseconds for minimal-contract retry (>=0)',
                'ai_conversation',
                NULL
            )
            ON CONFLICT (config_key) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    """Remove minimal-contract retry configs from system_configs."""
    if not _table_exists("system_configs"):
        return

    op.execute(
        sa.text(
            """
            DELETE FROM system_configs
            WHERE config_key IN (
                'ai_llm_min_contract_retry_enabled',
                'ai_llm_min_contract_retry_max_attempts',
                'ai_llm_min_contract_retry_backoff_ms'
            )
            """
        )
    )
