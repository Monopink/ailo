"""Unify invitation reward trigger to invite_bind_success only.

Revision ID: 20260427_01
Revises: 20260426_00
Create Date: 2026-04-27 00:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260427_01"
down_revision: str | Sequence[str] | None = "20260426_00"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Collapse invite trigger event to a single bind-success event."""
    op.execute(
        """
        DO $$
        DECLARE
            v_entitlement_type_id INTEGER;
        BEGIN
            SELECT id
            INTO v_entitlement_type_id
            FROM entitlement_types
            WHERE code = 'ai_contact_limit' AND status = 1
            LIMIT 1;

            IF v_entitlement_type_id IS NULL THEN
                RAISE EXCEPTION 'Missing active entitlement type: ai_contact_limit';
            END IF;
        END;
        $$;
        """
    )

    op.execute(
        """
        WITH duplicate_pairs AS (
            SELECT old_rule.id AS old_rule_id, new_rule.id AS new_rule_id
            FROM growth_reward_rules old_rule
            JOIN growth_reward_rules new_rule
              ON old_rule.trigger_event = 2
             AND new_rule.trigger_event = 1
             AND old_rule.target_role = new_rule.target_role
             AND old_rule.scope_type = new_rule.scope_type
             AND old_rule.scope_id = new_rule.scope_id
             AND old_rule.entitlement_type_id = new_rule.entitlement_type_id
             AND old_rule.priority = new_rule.priority
        )
        UPDATE growth_reward_applies applies
        SET rule_id = duplicate_pairs.new_rule_id,
            trigger_event = 1
        FROM duplicate_pairs
        WHERE applies.rule_id = duplicate_pairs.old_rule_id
        """
    )

    op.execute(
        """
        DELETE FROM growth_reward_rules old_rule
        USING (
            SELECT old_rule.id AS old_rule_id
            FROM growth_reward_rules old_rule
            JOIN growth_reward_rules new_rule
              ON old_rule.trigger_event = 2
             AND new_rule.trigger_event = 1
             AND old_rule.target_role = new_rule.target_role
             AND old_rule.scope_type = new_rule.scope_type
             AND old_rule.scope_id = new_rule.scope_id
             AND old_rule.entitlement_type_id = new_rule.entitlement_type_id
             AND old_rule.priority = new_rule.priority
        ) duplicate_old
        WHERE old_rule.id = duplicate_old.old_rule_id
        """
    )

    op.execute(
        """
        UPDATE growth_reward_rules
        SET trigger_event = 1
        WHERE trigger_event = 2
        """
    )

    op.execute(
        """
        UPDATE growth_reward_applies
        SET trigger_event = 1
        WHERE trigger_event = 2
        """
    )

    op.execute(
        """
        WITH ai AS (
            SELECT id AS entitlement_type_id
            FROM entitlement_types
            WHERE code = 'ai_contact_limit' AND status = 1
            LIMIT 1
        )
        UPDATE growth_reward_rules rules
        SET status = 1
        FROM ai
        WHERE rules.trigger_event = 1
          AND rules.target_role IN (2, 3)
          AND rules.scope_type = 1
          AND rules.scope_id = 0
          AND rules.entitlement_type_id = ai.entitlement_type_id
          AND rules.status <> 1
        """
    )

    op.execute(
        """
        INSERT INTO growth_reward_rules (
            trigger_event,
            target_role,
            scope_type,
            scope_id,
            entitlement_type_id,
            delta_granted,
            max_rewards_per_actor,
            priority,
            status
        )
        SELECT 1, 2, 1, 0, et.id, 1, NULL, 100, 1
        FROM entitlement_types et
        WHERE et.code = 'ai_contact_limit' AND et.status = 1
        ON CONFLICT ON CONSTRAINT uq_growth_reward_rules_unique_slot DO NOTHING
        """
    )

    op.execute(
        """
        INSERT INTO growth_reward_rules (
            trigger_event,
            target_role,
            scope_type,
            scope_id,
            entitlement_type_id,
            delta_granted,
            max_rewards_per_actor,
            priority,
            status
        )
        SELECT 1, 3, 1, 0, et.id, 1, 3, 100, 1
        FROM entitlement_types et
        WHERE et.code = 'ai_contact_limit' AND et.status = 1
        ON CONFLICT ON CONSTRAINT uq_growth_reward_rules_unique_slot DO NOTHING
        """
    )

    op.execute(
        """
        ALTER TABLE growth_reward_rules
        DROP CONSTRAINT IF EXISTS ck_growth_reward_rules_trigger_event
        """
    )
    op.execute(
        """
        ALTER TABLE growth_reward_rules
        ADD CONSTRAINT ck_growth_reward_rules_trigger_event
        CHECK (trigger_event IN (1, 3, 4))
        """
    )

    op.execute(
        """
        ALTER TABLE growth_reward_rules
        DROP CONSTRAINT IF EXISTS ck_growth_reward_rules_invite_scope
        """
    )
    op.execute(
        """
        ALTER TABLE growth_reward_rules
        ADD CONSTRAINT ck_growth_reward_rules_invite_scope
        CHECK ((trigger_event <> 1) OR (scope_type = 1))
        """
    )

    op.execute(
        """
        ALTER TABLE growth_reward_applies
        DROP CONSTRAINT IF EXISTS ck_growth_reward_applies_trigger_event
        """
    )
    op.execute(
        """
        ALTER TABLE growth_reward_applies
        ADD CONSTRAINT ck_growth_reward_applies_trigger_event
        CHECK (trigger_event IN (1, 3, 4))
        """
    )


def downgrade() -> None:
    """Downgrade is intentionally unsupported."""
    raise RuntimeError("Downgrade is not supported for migration 20260427_01")
