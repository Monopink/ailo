"""Shared invitation reward policy rule resolver."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.growth import (
    GrowthRewardRuleStatus,
    GrowthRewardScopeType,
    GrowthRewardTargetRole,
    GrowthRewardTriggerEvent,
)
from app.models.entitlement import EntitlementType
from app.models.growth_reward import GrowthRewardRule
from app.services.entitlement.service import ENTITLEMENT_AI_CONTACT_LIMIT
from app.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class InvitationPolicyRules:
    """Invitation reward rules for invitee and inviter slots."""

    invitee_rule: GrowthRewardRule
    inviter_rule: GrowthRewardRule


async def _get_ai_contact_limit_entitlement_type_id(db: AsyncSession) -> int:
    stmt = (
        select(EntitlementType.id)
        .where(
            EntitlementType.code == ENTITLEMENT_AI_CONTACT_LIMIT,
            EntitlementType.status == 1,
        )
        .limit(1)
    )
    result = await db.execute(stmt)
    entitlement_type_id = result.scalar_one_or_none()
    if entitlement_type_id is None:
        logger.error(
            "invitation_policy_entitlement_type_missing", code=ENTITLEMENT_AI_CONTACT_LIMIT
        )
        raise ValueError("invitation_policy_entitlement_type_missing")
    return int(entitlement_type_id)


async def _get_unique_invitation_rule_for_target(
    db: AsyncSession,
    *,
    target_role: GrowthRewardTargetRole,
    entitlement_type_id: int,
    for_update: bool,
) -> GrowthRewardRule:
    stmt = (
        select(GrowthRewardRule)
        .where(
            GrowthRewardRule.trigger_event == int(GrowthRewardTriggerEvent.INVITE_BIND_SUCCESS),
            GrowthRewardRule.target_role == int(target_role),
            GrowthRewardRule.scope_type == int(GrowthRewardScopeType.GLOBAL),
            GrowthRewardRule.scope_id == 0,
            GrowthRewardRule.entitlement_type_id == entitlement_type_id,
            GrowthRewardRule.status == int(GrowthRewardRuleStatus.ACTIVE),
        )
        .order_by(GrowthRewardRule.priority.asc(), GrowthRewardRule.id.asc())
    )
    if for_update:
        stmt = stmt.with_for_update()
    result = await db.execute(stmt)
    rules = list(result.scalars().all())
    if len(rules) == 0:
        logger.error(
            "invitation_policy_rule_missing",
            target_role=int(target_role),
            entitlement_type_id=entitlement_type_id,
        )
        raise ValueError("invitation_policy_rule_missing")
    if len(rules) > 1:
        logger.error(
            "invitation_policy_rule_duplicated",
            target_role=int(target_role),
            entitlement_type_id=entitlement_type_id,
            active_rule_ids=[int(rule.id) for rule in rules],
        )
        raise ValueError("invitation_policy_rule_duplicated")
    return rules[0]


async def get_invitation_policy_rules(
    db: AsyncSession,
    *,
    for_update: bool,
) -> InvitationPolicyRules:
    """Load unique invitation reward rules for invitee and inviter slots."""
    entitlement_type_id = await _get_ai_contact_limit_entitlement_type_id(db)
    invitee_rule = await _get_unique_invitation_rule_for_target(
        db,
        target_role=GrowthRewardTargetRole.INVITEE,
        entitlement_type_id=entitlement_type_id,
        for_update=for_update,
    )
    inviter_rule = await _get_unique_invitation_rule_for_target(
        db,
        target_role=GrowthRewardTargetRole.INVITER,
        entitlement_type_id=entitlement_type_id,
        for_update=for_update,
    )
    return InvitationPolicyRules(invitee_rule=invitee_rule, inviter_rule=inviter_rule)
