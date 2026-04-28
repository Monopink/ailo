"""Enforce unique active invitation policy slots.

Revision ID: 20260427_02
Revises: 20260427_01
Create Date: 2026-04-27 02:10:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260427_02"
down_revision: str | Sequence[str] | None = "20260427_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply invitation slot guard plus entitlement/admin operation schema updates."""
    op.execute(
        """
        DO $$
        DECLARE
            v_entitlement_type_id INTEGER;
            v_role INTEGER;
            v_rule_ids TEXT;
            v_count INTEGER;
            v_role_name TEXT;
        BEGIN
            SELECT id
            INTO v_entitlement_type_id
            FROM entitlement_types
            WHERE code = 'ai_contact_limit' AND status = 1
            LIMIT 1;

            IF v_entitlement_type_id IS NULL THEN
                RAISE EXCEPTION
                    'Missing active entitlement type: ai_contact_limit';
            END IF;

            FOR v_role, v_rule_ids, v_count IN
                SELECT
                    rules.target_role,
                    string_agg(rules.id::TEXT, ',' ORDER BY rules.id),
                    COUNT(*)
                FROM growth_reward_rules AS rules
                WHERE rules.trigger_event = 1
                  AND rules.target_role IN (2, 3)
                  AND rules.scope_type = 1
                  AND rules.scope_id = 0
                  AND rules.entitlement_type_id = v_entitlement_type_id
                  AND rules.status = 1
                GROUP BY rules.target_role
                HAVING COUNT(*) > 1
            LOOP
                v_role_name := CASE
                    WHEN v_role = 2 THEN 'invitee'
                    WHEN v_role = 3 THEN 'inviter'
                    ELSE 'unknown'
                END;
                RAISE EXCEPTION
                    'Duplicate active invitation rules for role=% (%), ids=%',
                    v_role,
                    v_role_name,
                    v_rule_ids;
            END LOOP;
        END;
        $$;
        """
    )

    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_growth_reward_rules_active_invite_slot
        ON growth_reward_rules (
            trigger_event,
            target_role,
            scope_type,
            scope_id,
            entitlement_type_id
        )
        WHERE status = 1
          AND trigger_event = 1
          AND target_role IN (2, 3)
          AND scope_type = 1
          AND scope_id = 0
        """
    )

    op.execute(
        """
        ALTER TABLE admin_operation_logs
        ADD COLUMN IF NOT EXISTS operation_meta JSONB NULL
        """
    )

    op.execute(
        """
        ALTER TABLE entitlement_reason_codes
        ADD COLUMN IF NOT EXISTS applies_to VARCHAR(16)
        """
    )
    op.execute(
        """
        UPDATE entitlement_reason_codes
        SET applies_to = CASE code
            WHEN 'admin_activity_reward' THEN 'grant'
            WHEN 'admin_bug_compensation' THEN 'grant'
            WHEN 'admin_customer_care' THEN 'grant'
            WHEN 'admin_ops_correction' THEN 'adjust'
            ELSE 'both'
        END
        WHERE applies_to IS NULL OR applies_to = ''
        """
    )
    op.execute(
        """
        ALTER TABLE entitlement_reason_codes
        ALTER COLUMN applies_to SET DEFAULT 'both'
        """
    )
    op.execute(
        """
        ALTER TABLE entitlement_reason_codes
        ALTER COLUMN applies_to SET NOT NULL
        """
    )
    op.execute(
        """
        ALTER TABLE entitlement_reason_codes
        ADD CONSTRAINT ck_entitlement_reason_codes_applies_to
        CHECK (applies_to IN ('grant', 'adjust', 'both'))
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_entitlement_reason_codes_applies_to
        ON entitlement_reason_codes (applies_to)
        """
    )

    op.execute(
        """
        INSERT INTO entitlement_reason_codes (
            code,
            display_name,
            description,
            is_system,
            status,
            applies_to
        )
        VALUES
            (
                'admin_penalty_deduction',
                'Penalty Deduction',
                'Entitlement deduction due to policy violations',
                TRUE,
                1,
                'adjust'
            ),
            (
                'admin_abuse_control',
                'Abuse Control Reclaim',
                'Entitlement reclaimed after abuse is detected by risk control',
                TRUE,
                1,
                'adjust'
            )
        ON CONFLICT (code) DO UPDATE
        SET
            display_name = EXCLUDED.display_name,
            description = EXCLUDED.description,
            is_system = TRUE,
            status = 1,
            applies_to = 'adjust'
        """
    )


def downgrade() -> None:
    """Downgrade is intentionally unsupported."""
    raise RuntimeError("Downgrade is not supported for migration 20260427_02")
