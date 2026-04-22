"""Unified growth reward execution service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.entitlement import user_entitlement_ledger as entitlement_ledger_crud
from app.crud.growth_reward import growth_reward_rule as growth_reward_rule_crud
from app.crud.invite import invite_binding as invite_binding_crud
from app.enums.growth import GrowthRewardTargetRole, GrowthRewardTriggerEvent
from app.models.entitlement import EntitlementType, UserEntitlementLedger
from app.models.user import User
from app.services.entitlement.service import (
    ENTITLEMENT_AI_CONTACT_LIMIT,
    ENTITLEMENT_SOURCE_CAMPAIGN_ATTRIBUTION,
    ENTITLEMENT_SOURCE_INVITE_BIND_INVITEE,
    ENTITLEMENT_SOURCE_INVITE_BIND_INVITER,
    ENTITLEMENT_SOURCE_REDEEM_CODE_CLAIM,
    grant_entitlement,
)
from app.services.system_config import get_config


@dataclass(frozen=True, slots=True)
class RewardApplyResult:
    """Result for one reward execution."""

    total_ai_contact_limit_delta: int
    applied_rule_ids: list[int]


NEW_USER_WINDOW_DAYS_CONFIG_KEY = "growth_new_user_reward_window_days"
NEW_USER_REWARD_CAP_TOTAL_CONFIG_KEY = "growth_new_user_reward_cap_total"
DEFAULT_NEW_USER_WINDOW_DAYS = 7
DEFAULT_NEW_USER_REWARD_CAP_TOTAL = 5
REWARD_SOURCE_TYPES = {
    ENTITLEMENT_SOURCE_INVITE_BIND_INVITEE,
    ENTITLEMENT_SOURCE_INVITE_BIND_INVITER,
    ENTITLEMENT_SOURCE_CAMPAIGN_ATTRIBUTION,
    ENTITLEMENT_SOURCE_REDEEM_CODE_CLAIM,
}
INVITE_BIND_SUCCESS_EVENT = int(GrowthRewardTriggerEvent.INVITE_BIND_SUCCESS)
INVITEE_SETUP_COMPLETED_EVENT = int(GrowthRewardTriggerEvent.INVITEE_SETUP_COMPLETED)
CAMPAIGN_ATTRIBUTION_EVENT = int(GrowthRewardTriggerEvent.CAMPAIGN_ATTRIBUTION_FIRST_TOUCH)
REDEEM_CODE_CLAIM_EVENT = int(GrowthRewardTriggerEvent.REDEEM_CODE_CLAIM_SUCCESS)


def _source_type_from_event(trigger_event: int) -> str:
    if trigger_event == INVITE_BIND_SUCCESS_EVENT:
        return ENTITLEMENT_SOURCE_INVITE_BIND_INVITEE
    if trigger_event == INVITEE_SETUP_COMPLETED_EVENT:
        return ENTITLEMENT_SOURCE_INVITE_BIND_INVITER
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


async def _get_optional_positive_int(
    db: AsyncSession,
    *,
    key: str,
    default: int,
) -> int:
    raw = await get_config(db, key=key, required=False)
    if isinstance(raw, int):
        return raw if raw > 0 else default
    if isinstance(raw, str):
        try:
            parsed = int(raw)
        except ValueError:
            return default
        return parsed if parsed > 0 else default
    return default


async def _cap_delta_for_new_user_reward_window(
    db: AsyncSession,
    *,
    user_id: int,
    delta: int,
    occurred_at: datetime,
) -> int:
    if delta <= 0:
        return 0
    window_days = await _get_optional_positive_int(
        db,
        key=NEW_USER_WINDOW_DAYS_CONFIG_KEY,
        default=DEFAULT_NEW_USER_WINDOW_DAYS,
    )
    reward_cap_total = await _get_optional_positive_int(
        db,
        key=NEW_USER_REWARD_CAP_TOTAL_CONFIG_KEY,
        default=DEFAULT_NEW_USER_REWARD_CAP_TOTAL,
    )
    if reward_cap_total <= 0:
        return 0

    user_row = await db.execute(select(User.created_at).where(User.id == user_id))
    user_created_at = user_row.scalar_one_or_none()
    if user_created_at is None:
        return delta

    window_end = user_created_at + timedelta(days=window_days)
    if occurred_at >= window_end:
        return delta

    total_reward_query = await db.execute(
        select(func.coalesce(func.sum(UserEntitlementLedger.delta_granted), 0)).where(
            UserEntitlementLedger.user_id == user_id,
            UserEntitlementLedger.action_type == 1,
            UserEntitlementLedger.source_type.in_(REWARD_SOURCE_TYPES),
            UserEntitlementLedger.created_at >= user_created_at,
            UserEntitlementLedger.created_at < window_end,
        )
    )
    rewarded_total_raw = total_reward_query.scalar_one()
    rewarded_total = (
        int(rewarded_total_raw)
        if isinstance(rewarded_total_raw, int)
        else int(rewarded_total_raw or 0)
    )
    remaining = reward_cap_total - rewarded_total
    if remaining <= 0:
        return 0
    return min(delta, remaining)


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
    source_type = _source_type_from_event(trigger_event)
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
        delta = await _cap_delta_for_new_user_reward_window(
            db,
            user_id=actor_user_id,
            delta=delta,
            occurred_at=at,
        )
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


async def apply_inviter_rewards_for_invitee_setup(
    db: AsyncSession,
    *,
    invitee_user_id: int,
) -> RewardApplyResult:
    """Apply inviter reward when invitee completes setup for the first time."""
    binding = await invite_binding_crud.get_with_inviter_by_invitee_user_id(
        db, invitee_user_id=invitee_user_id
    )
    if binding is None:
        return RewardApplyResult(total_ai_contact_limit_delta=0, applied_rule_ids=[])
    binding_id, inviter_user_id = binding
    return await apply_growth_rewards(
        db,
        trigger_event=int(GrowthRewardTriggerEvent.INVITEE_SETUP_COMPLETED),
        target_role=int(GrowthRewardTargetRole.INVITER),
        actor_user_id=inviter_user_id,
        source_id=binding_id,
        idempotency_scope=f"invitee_setup:{invitee_user_id}",
        event_payload={"invitee_user_id": invitee_user_id, "binding_id": binding_id},
    )
