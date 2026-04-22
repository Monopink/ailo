"""Growth reward related CRUD operations."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.growth import GrowthRewardRuleStatus, GrowthRewardScopeType
from app.models.growth_reward import GrowthRewardApply, GrowthRewardRule


class CRUDGrowthRewardRule:
    """CRUD helpers for growth_reward_rules."""

    async def list_active_rules(
        self,
        db: AsyncSession,
        *,
        trigger_event: int,
        target_role: int,
        campaign_id: int | None,
        redeem_batch_id: int | None,
        at: datetime | None = None,
    ) -> list[GrowthRewardRule]:
        """List active rules ordered by execution priority."""
        now = at or datetime.now(UTC)
        if campaign_id is not None and redeem_batch_id is not None:
            raise ValueError("Growth reward scope is ambiguous")

        if campaign_id is not None:
            scope_type = int(GrowthRewardScopeType.CAMPAIGN)
            scope_id = campaign_id
        elif redeem_batch_id is not None:
            scope_type = int(GrowthRewardScopeType.REDEEM_BATCH)
            scope_id = redeem_batch_id
        else:
            scope_type = int(GrowthRewardScopeType.GLOBAL)
            scope_id = 0

        stmt = (
            select(GrowthRewardRule)
            .where(
                GrowthRewardRule.status == int(GrowthRewardRuleStatus.ACTIVE),
                GrowthRewardRule.trigger_event == trigger_event,
                GrowthRewardRule.target_role == target_role,
                GrowthRewardRule.scope_type == scope_type,
                GrowthRewardRule.scope_id == scope_id,
                (GrowthRewardRule.starts_at.is_(None) | (GrowthRewardRule.starts_at <= now)),
                (GrowthRewardRule.ends_at.is_(None) | (GrowthRewardRule.ends_at > now)),
            )
            .order_by(GrowthRewardRule.priority.asc(), GrowthRewardRule.id.asc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def count_actor_applied_rewards(
        self,
        db: AsyncSession,
        *,
        actor_user_id: int,
        rule_id: int,
    ) -> int:
        """Count already-applied rewards for one actor under a rule."""
        stmt = (
            select(func.count())
            .select_from(GrowthRewardApply)
            .where(
                GrowthRewardApply.actor_user_id == actor_user_id,
                GrowthRewardApply.rule_id == rule_id,
            )
        )
        result = await db.execute(stmt)
        count = result.scalar_one()
        return int(count) if isinstance(count, int) else int(count or 0)

    async def create_apply_record(
        self,
        db: AsyncSession,
        *,
        rule_id: int,
        trigger_event: int,
        target_role: int,
        actor_user_id: int,
        beneficiary_user_id: int,
        source_type: str,
        source_id: int,
        scope_type: int,
        scope_id: int,
        entitlement_type_id: int,
        delta_granted: int,
        ledger_id: int,
        idempotency_key: str,
        event_payload: dict[str, object] | None,
    ) -> GrowthRewardApply:
        """Create one structured reward apply record."""
        obj = GrowthRewardApply(
            rule_id=rule_id,
            trigger_event=trigger_event,
            target_role=target_role,
            actor_user_id=actor_user_id,
            beneficiary_user_id=beneficiary_user_id,
            source_type=source_type,
            source_id=source_id,
            scope_type=scope_type,
            scope_id=scope_id,
            entitlement_type_id=entitlement_type_id,
            delta_granted=delta_granted,
            ledger_id=ledger_id,
            idempotency_key=idempotency_key,
            event_payload=event_payload,
        )
        db.add(obj)
        await db.flush()
        return obj


growth_reward_rule = CRUDGrowthRewardRule()
