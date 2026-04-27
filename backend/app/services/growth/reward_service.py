"""Unified growth reward execution service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.entitlement import user_entitlement_ledger as entitlement_ledger_crud
from app.crud.growth_reward import growth_reward_rule as growth_reward_rule_crud
from app.enums.growth import GrowthRewardTargetRole, GrowthRewardTriggerEvent
from app.models.entitlement import EntitlementType
from app.models.user import User
from app.services.entitlement.service import (
    ENTITLEMENT_AI_CONTACT_LIMIT,
    ENTITLEMENT_SOURCE_CAMPAIGN_ATTRIBUTION,
    ENTITLEMENT_SOURCE_INVITE_BIND_INVITEE,
    ENTITLEMENT_SOURCE_INVITE_BIND_INVITER,
    ENTITLEMENT_SOURCE_REDEEM_CODE_CLAIM,
    grant_entitlement,
)


@dataclass(frozen=True, slots=True)
class RewardApplyResult:
    """Result for one reward execution."""

    total_ai_contact_limit_delta: int
    applied_rule_ids: list[int]


INVITE_BIND_SUCCESS_EVENT = int(GrowthRewardTriggerEvent.INVITE_BIND_SUCCESS)
CAMPAIGN_ATTRIBUTION_EVENT = int(GrowthRewardTriggerEvent.CAMPAIGN_ATTRIBUTION_FIRST_TOUCH)
REDEEM_CODE_CLAIM_EVENT = int(GrowthRewardTriggerEvent.REDEEM_CODE_CLAIM_SUCCESS)


def _source_type_from_event(*, trigger_event: int, target_role: int) -> str:
    if trigger_event == INVITE_BIND_SUCCESS_EVENT:
        if target_role == int(GrowthRewardTargetRole.INVITER):
            return ENTITLEMENT_SOURCE_INVITE_BIND_INVITER
        return ENTITLEMENT_SOURCE_INVITE_BIND_INVITEE
    if trigger_event == CAMPAIGN_ATTRIBUTION_EVENT:
        return ENTITLEMENT_SOURCE_CAMPAIGN_ATTRIBUTION
    if trigger_event == REDEEM_CODE_CLAIM_EVENT:
        return ENTITLEMENT_SOURCE_REDEEM_CODE_CLAIM
    raise ValueError("Unsupported reward trigger event")


async def _get_active_entitlement_code_map(
    db: AsyncSession,
    *,
    entitlement_type_ids: set[int],
) -> dict[int, str]:
    if len(entitlement_type_ids) == 0:
        return {}
    result = await db.execute(
        select(EntitlementType.id, EntitlementType.code).where(
            EntitlementType.id.in_(entitlement_type_ids),
            EntitlementType.status == 1,
        )
    )
    rows = result.all()
    return {int(row[0]): str(row[1]) for row in rows}


async def apply_growth_rewards(
    db: AsyncSession,
    *,
    trigger_event: int,
    target_role: int,
    actor_user_id: int,
    source_id: int,
    idempotency_scope: str,
    campaign_id: int | None = None,
    redeem_batch_id: int | None = None,
    event_payload: dict[str, object] | None = None,
    occurred_at: datetime | None = None,
) -> RewardApplyResult:
    """Apply active growth rewards for one trigger and actor."""
    at = occurred_at or datetime.now(UTC)
    rules = await growth_reward_rule_crud.list_active_rules(
        db,
        trigger_event=trigger_event,
        target_role=target_role,
        campaign_id=campaign_id,
        redeem_batch_id=redeem_batch_id,
        at=at,
    )
    if len(rules) == 0:
        return RewardApplyResult(total_ai_contact_limit_delta=0, applied_rule_ids=[])

    entitlement_map = await _get_active_entitlement_code_map(
        db, entitlement_type_ids={int(rule.entitlement_type_id) for rule in rules}
    )
    source_type = _source_type_from_event(trigger_event=trigger_event, target_role=target_role)
    applied_rule_ids: list[int] = []
    total_ai_contact_limit_delta = 0
    actor_locked = False

    for rule in rules:
        if int(rule.delta_granted) <= 0:
            continue
        rule_id = int(rule.id)
        max_rewards_per_actor = (
            int(rule.max_rewards_per_actor) if rule.max_rewards_per_actor is not None else None
        )
        if max_rewards_per_actor is not None:
            if not actor_locked:
                await db.execute(select(User.id).where(User.id == actor_user_id).with_for_update())
                actor_locked = True
            applied_rewards = await growth_reward_rule_crud.count_actor_applied_rewards(
                db,
                actor_user_id=actor_user_id,
                rule_id=rule_id,
            )
            if applied_rewards >= max_rewards_per_actor:
                continue

        entitlement_code = entitlement_map.get(int(rule.entitlement_type_id))
        if entitlement_code is None:
            continue

        delta = int(rule.delta_granted)
        if delta <= 0:
            continue
        idempotency_key = f"{source_type}:{idempotency_scope}:{source_id}:{rule_id}:{actor_user_id}"
        payload: dict[str, object] = {
            "rule_id": rule_id,
            "trigger_event": trigger_event,
            "target_role": target_role,
            "campaign_id": campaign_id,
            "redeem_batch_id": redeem_batch_id,
        }
        if event_payload is not None:
            payload["trigger_payload"] = event_payload
        applied = await grant_entitlement(
            db,
            user_id=actor_user_id,
            entitlement_type_code=entitlement_code,
            value=delta,
            source_type=source_type,
            source_id=source_id,
            idempotency_key=idempotency_key,
            event_payload=payload,
        )
        if not applied:
            continue
        ledger = await entitlement_ledger_crud.get_by_idempotency_key(
            db,
            user_id=actor_user_id,
            entitlement_type_id=int(rule.entitlement_type_id),
            idempotency_key=idempotency_key,
        )
        if ledger is None:
            raise RuntimeError("Reward ledger not found for growth reward apply record")
        await growth_reward_rule_crud.create_apply_record(
            db,
            rule_id=rule_id,
            trigger_event=trigger_event,
            target_role=target_role,
            actor_user_id=actor_user_id,
            beneficiary_user_id=actor_user_id,
            source_type=source_type,
            source_id=source_id,
            scope_type=int(rule.scope_type),
            scope_id=int(rule.scope_id),
            entitlement_type_id=int(rule.entitlement_type_id),
            delta_granted=delta,
            ledger_id=int(ledger.id),
            idempotency_key=idempotency_key,
            event_payload=payload,
        )
        applied_rule_ids.append(rule_id)
        if entitlement_code == ENTITLEMENT_AI_CONTACT_LIMIT:
            total_ai_contact_limit_delta += delta

    return RewardApplyResult(
        total_ai_contact_limit_delta=total_ai_contact_limit_delta,
        applied_rule_ids=applied_rule_ids,
    )
