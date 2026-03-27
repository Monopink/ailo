"""Alembic revision 20260326_01 (alert events).

Revises: 20260326_00
Create Date: 2026-03-26 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260326_01"
down_revision: str | Sequence[str] | None = "20260326_00"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return inspector.has_table(table_name)


def _index_exists(table_name: str, index_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(idx["name"] == index_name for idx in inspector.get_indexes(table_name))


def upgrade() -> None:
    """Create alert_events / alert_event_entities and seed cleanup configs."""
    if not _table_exists("alert_events"):
        op.create_table(
            "alert_events",
            sa.Column("id", sa.BigInteger(), primary_key=True),
            sa.Column("event_type", sa.String(length=120), nullable=False),
            sa.Column("domain", sa.String(length=40), nullable=False),
            sa.Column("severity_level", sa.SmallInteger(), nullable=False),
            sa.Column("dedupe_key", sa.String(length=255), nullable=True),
            sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                nullable=False,
                server_default=sa.text("NOW()"),
            ),
            sa.CheckConstraint(
                "severity_level IN (10, 20, 30, 40, 50)",
                name="ck_alert_events_severity_level",
            ),
        )

    if not _index_exists("alert_events", "idx_alert_events_event_type_created_at"):
        op.create_index(
            "idx_alert_events_event_type_created_at",
            "alert_events",
            ["event_type", "created_at"],
            unique=False,
        )

    if not _index_exists("alert_events", "idx_alert_events_domain_created_at"):
        op.create_index(
            "idx_alert_events_domain_created_at",
            "alert_events",
            ["domain", "created_at"],
            unique=False,
        )

    if not _index_exists("alert_events", "idx_alert_events_created_at"):
        op.create_index(
            "idx_alert_events_created_at",
            "alert_events",
            ["created_at"],
            unique=False,
        )

    if not _index_exists("alert_events", "idx_alert_events_dedupe_key"):
        op.create_index(
            "idx_alert_events_dedupe_key",
            "alert_events",
            ["dedupe_key"],
            unique=False,
        )

    if not _index_exists("alert_events", "uq_alert_events_event_type_dedupe_key"):
        op.create_index(
            "uq_alert_events_event_type_dedupe_key",
            "alert_events",
            ["event_type", "dedupe_key"],
            unique=True,
            postgresql_where=sa.text("dedupe_key IS NOT NULL"),
        )

    if not _table_exists("alert_event_entities"):
        op.create_table(
            "alert_event_entities",
            sa.Column("id", sa.BigInteger(), primary_key=True),
            sa.Column("event_id", sa.BigInteger(), nullable=False),
            sa.Column("entity_type", sa.String(length=40), nullable=False),
            sa.Column("entity_id", sa.String(length=128), nullable=False),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                nullable=False,
                server_default=sa.text("NOW()"),
            ),
        )

    if not _index_exists("alert_event_entities", "idx_alert_event_entities_event_id"):
        op.create_index(
            "idx_alert_event_entities_event_id",
            "alert_event_entities",
            ["event_id"],
            unique=False,
        )

    if not _index_exists("alert_event_entities", "idx_alert_event_entities_type_id_created_at"):
        op.create_index(
            "idx_alert_event_entities_type_id_created_at",
            "alert_event_entities",
            ["entity_type", "entity_id", "created_at"],
            unique=False,
        )

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
                'alerting_cleanup_enabled',
                'true',
                'true',
                3,
                'Enable alert_events cleanup worker',
                'alerting',
                NULL
            ),
            (
                'alerting_cleanup_interval_seconds',
                '3600',
                '3600',
                2,
                'Cleanup interval in seconds for alert_events (>=1)',
                'alerting',
                NULL
            ),
            (
                'alerting_default_retention_days',
                '30',
                '30',
                2,
                'Default retention days for alert_events (>=0)',
                'alerting',
                NULL
            )
            ON CONFLICT (config_key) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    """Drop alert_events / alert_event_entities and remove alerting cleanup configs."""
    if _table_exists("system_configs"):
        op.execute(
            sa.text(
                """
                DELETE FROM system_configs
                WHERE config_key IN (
                    'alerting_cleanup_enabled',
                    'alerting_cleanup_interval_seconds',
                    'alerting_default_retention_days'
                )
                """
            )
        )

    if _table_exists("alert_event_entities"):
        if _index_exists("alert_event_entities", "idx_alert_event_entities_type_id_created_at"):
            op.drop_index(
                "idx_alert_event_entities_type_id_created_at", table_name="alert_event_entities"
            )
        if _index_exists("alert_event_entities", "idx_alert_event_entities_event_id"):
            op.drop_index(
                "idx_alert_event_entities_event_id", table_name="alert_event_entities"
            )
        op.drop_table("alert_event_entities")

    if not _table_exists("alert_events"):
        return

    if _index_exists("alert_events", "uq_alert_events_event_type_dedupe_key"):
        op.drop_index("uq_alert_events_event_type_dedupe_key", table_name="alert_events")
    if _index_exists("alert_events", "idx_alert_events_dedupe_key"):
        op.drop_index("idx_alert_events_dedupe_key", table_name="alert_events")
    if _index_exists("alert_events", "idx_alert_events_created_at"):
        op.drop_index("idx_alert_events_created_at", table_name="alert_events")
    if _index_exists("alert_events", "idx_alert_events_domain_created_at"):
        op.drop_index("idx_alert_events_domain_created_at", table_name="alert_events")
    if _index_exists("alert_events", "idx_alert_events_event_type_created_at"):
        op.drop_index("idx_alert_events_event_type_created_at", table_name="alert_events")

    op.drop_table("alert_events")
