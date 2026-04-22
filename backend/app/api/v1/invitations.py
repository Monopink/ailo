"""Invitation API endpoints."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.crud.entitlement import entitlement_type as entitlement_type_crud
from app.crud.growth_reward import growth_reward_rule as growth_reward_rule_crud
from app.crud.invite import invite_binding as invite_binding_crud
from app.crud.invite import invite_code as invite_code_crud
from app.crud.invite import invite_event as invite_event_crud
from app.crud.invite import invite_share_template as invite_share_template_crud
from app.enums.growth import GrowthRewardScopeType, GrowthRewardTargetRole, GrowthRewardTriggerEvent
from app.enums.invite import InviteEventType, InviteResolveCodeType
from app.models.user import User
from app.schemas.invitation import (
    InvitationBindingStatusResponse,
    InvitationBindRequest,
    InvitationBindResponse,
    InvitationCodeResponse,
    InvitationEventTrackRequest,
    InvitationEventTrackResponse,
    InvitationIntakeRequest,
    InvitationIntakeResponse,
    InvitationResolveRequest,
    InvitationResolveResponse,
    InvitationShareCard,
    InvitationShareFullResponse,
    InvitationStatsResponse,
)
from app.services.entitlement.service import ENTITLEMENT_AI_CONTACT_LIMIT
from app.services.growth.reward_service import apply_growth_rewards
from app.services.invitation.intake import (
    normalize_event_source_or_raise,
    normalize_invite_code_or_raise,
)
from app.services.invitation.intake_orchestrator import orchestrate_invitation_intake
from app.services.invitation.share_card import resolve_invite_share_card
from app.services.security.rate_limiter import check_rate_limit
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/invitations", tags=["Invitations"])

USER_INVITE_CODE_LENGTH = 6
USER_INVITE_CODE_CHARSET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
INVITE_SHARE_CODE_PLACEHOLDER = "{{code}}"
INVITE_SHARE_LINK_PLACEHOLDER = "{{link}}"
INVITE_CAP_REACHED_ERROR = "邀请人数已达上限"


def _generate_user_invite_code() -> str:
    return "".join(secrets.choice(USER_INVITE_CODE_CHARSET) for _ in range(USER_INVITE_CODE_LENGTH))


def _event_type_to_code(raw: str) -> InviteEventType:
    mapping: dict[str, InviteEventType] = {
        "resolve_valid": InviteEventType.RESOLVE_VALID,
        "bind_success": InviteEventType.BIND_SUCCESS,
        "copy_command": InviteEventType.COPY_COMMAND,
        "share_wechat": InviteEventType.SHARE_WECHAT,
    }
    if raw not in mapping:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请求参数错误")
    return mapping[raw]


async def _check_invite_resolve_rate_limit_or_raise(*, user_id: int, db: AsyncSession) -> None:
    allowed, _reason, _retry_after = await check_rate_limit(str(user_id), "invite_code_resolve", db)
    if allowed:
        return
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="操作过于频繁，请稍后再试"
    )


async def _check_invite_bind_rate_limit_or_raise(*, user_id: int, db: AsyncSession) -> None:
    allowed, _reason, _retry_after = await check_rate_limit(str(user_id), "invite_code_bind", db)
    if allowed:
        return
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="操作过于频繁，请稍后再试"
    )


async def _lock_users_in_order(db: AsyncSession, *, user_ids: list[int]) -> None:
    ordered_user_ids = sorted({int(user_id) for user_id in user_ids})
    if len(ordered_user_ids) == 0:
        return
    await db.execute(
        select(User.id).where(User.id.in_(ordered_user_ids)).order_by(User.id).with_for_update()
    )


async def _get_or_create_user_invite_code(
    db: AsyncSession,
    *,
    user_id: int,
) -> str:
    existing = await invite_code_crud.get_by_owner_user_id(db, user_id=user_id)
    if existing is not None:
        return existing.code

    for _ in range(30):
        code = _generate_user_invite_code()
        if await invite_code_crud.get_by_code(db, code=code) is not None:
            continue
        try:
            created = await invite_code_crud.create_user_code(db, user_id=user_id, code=code)
            return created.code
        except IntegrityError:
            await db.rollback()
            winner = await invite_code_crud.get_by_owner_user_id(db, user_id=user_id)
            if winner is not None:
                return winner.code
            continue

    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="系统错误")


async def _is_bindable(
    db: AsyncSession,
    *,
    invitee_user: User,
    inviter_user_id: int | None,
) -> bool:
    existing = await invite_binding_crud.get_by_invitee_user_id(db, invitee_user_id=invitee_user.id)
    if existing is not None:
        return False
    if inviter_user_id is None:
        return False
    if inviter_user_id == invitee_user.id:
        return False
    return not await invite_binding_crud.is_inviter_of(
        db,
        inviter_user_id=invitee_user.id,
        invitee_user_id=inviter_user_id,
    )


class _InviterRewardPolicy:
    def __init__(
        self,
        *,
        reward_contact_limit_per_invite: int,
        max_invite_count: int | None,
    ) -> None:
        self.reward_contact_limit_per_invite = reward_contact_limit_per_invite
        self.max_invite_count = max_invite_count


async def _get_inviter_reward_policy(db: AsyncSession) -> _InviterRewardPolicy:
    entitlement_type = await entitlement_type_crud.get_by_code(
        db, code=ENTITLEMENT_AI_CONTACT_LIMIT
    )
    if entitlement_type is None or int(entitlement_type.status) != 1:
        logger.error("invite_stats_entitlement_type_missing", code=ENTITLEMENT_AI_CONTACT_LIMIT)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="系统错误")

    rules = await growth_reward_rule_crud.list_active_rules(
        db,
        trigger_event=int(GrowthRewardTriggerEvent.INVITEE_SETUP_COMPLETED),
        target_role=int(GrowthRewardTargetRole.INVITER),
        campaign_id=None,
        redeem_batch_id=None,
    )

    selected_rule = next(
        (
            rule
            for rule in rules
            if int(rule.scope_type) == int(GrowthRewardScopeType.GLOBAL)
            and int(rule.scope_id) == 0
            and int(rule.entitlement_type_id) == int(entitlement_type.id)
        ),
        None,
    )
    if selected_rule is None:
        logger.error("invite_stats_rule_missing")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="系统错误")

    reward_contact_limit_per_invite = int(selected_rule.delta_granted)
    if reward_contact_limit_per_invite < 0:
        logger.error(
            "invite_stats_rule_delta_invalid",
            rule_id=int(selected_rule.id),
            delta=reward_contact_limit_per_invite,
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="系统错误")
    max_invite_count = (
        int(selected_rule.max_rewards_per_actor)
        if selected_rule.max_rewards_per_actor is not None
        else None
    )
    if max_invite_count is not None and max_invite_count < 1:
        logger.error(
            "invite_stats_rule_cap_invalid",
            rule_id=int(selected_rule.id),
            max_rewards_per_actor=max_invite_count,
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="系统错误")

    return _InviterRewardPolicy(
        reward_contact_limit_per_invite=reward_contact_limit_per_invite,
        max_invite_count=max_invite_count,
    )


@router.get("/binding-status", response_model=InvitationBindingStatusResponse)
async def get_invitation_binding_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvitationBindingStatusResponse:
    """Get whether current user has already bound an invite code."""
    try:
        binding = await invite_binding_crud.get_by_invitee_user_id(
            db,
            invitee_user_id=int(current_user.id),
        )
        return InvitationBindingStatusResponse(is_bound=binding is not None)
    except HTTPException:
        raise
    except Exception as exc:
        await db.rollback()
        logger.error(
            "invite_binding_status_get_failed",
            user_id=int(current_user.id),
            error=str(exc),
            exc_info=True,
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="系统错误")


@router.get("/code", response_model=InvitationCodeResponse)
async def get_my_invite_code(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvitationCodeResponse:
    """Get or create the current user's invite code."""
    try:
        code = await _get_or_create_user_invite_code(db, user_id=current_user.id)
        return InvitationCodeResponse(code=code)
    except HTTPException:
        raise
    except Exception as exc:
        await db.rollback()
        logger.error(
            "invite_code_create_failed",
            user_id=current_user.id,
            error=str(exc),
            exc_info=True,
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="系统错误")


@router.get("/stats", response_model=InvitationStatsResponse)
async def get_invitation_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvitationStatsResponse:
    """Get invitation stats for current user."""
    try:
        policy = await _get_inviter_reward_policy(db)
        success_invite_count = await invite_binding_crud.count_success_by_inviter_user_id(
            db,
            inviter_user_id=int(current_user.id),
        )
        max_reward_contact_limit_total = (
            policy.max_invite_count * policy.reward_contact_limit_per_invite
            if policy.max_invite_count is not None
            else None
        )
        rewarded_contact_limit_total = success_invite_count * policy.reward_contact_limit_per_invite
        return InvitationStatsResponse(
            success_invite_count=success_invite_count,
            max_invite_count=policy.max_invite_count,
            reward_contact_limit_per_invite=policy.reward_contact_limit_per_invite,
            max_reward_contact_limit_total=max_reward_contact_limit_total,
            rewarded_contact_limit_total=rewarded_contact_limit_total,
        )
    except HTTPException:
        raise
    except Exception as exc:
        await db.rollback()
        logger.error(
            "invite_stats_get_failed",
            user_id=int(current_user.id),
            error=str(exc),
            exc_info=True,
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="系统错误")


@router.get("/share", response_model=InvitationShareFullResponse)
async def get_invitation_share(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvitationShareFullResponse:
    """Get invite share payload."""
    try:
        code = await _get_or_create_user_invite_code(db, user_id=current_user.id)

        template_obj = await invite_share_template_crud.get_one_active_random(db, locale="zh-CN")
        if template_obj is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="系统错误",
            )

        template = template_obj.template_text.strip()

        link = f"{str(request.base_url).rstrip('/')}/i/{code}"
        text = template.replace(INVITE_SHARE_CODE_PLACEHOLDER, code).replace(
            INVITE_SHARE_LINK_PLACEHOLDER, link
        )

        share_card = await resolve_invite_share_card(db, code=code)
        if share_card is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="系统错误",
            )

        return InvitationShareFullResponse(
            code=code,
            text=text,
            link=link,
            share_card=InvitationShareCard(
                title=share_card.title,
                path=share_card.path,
                image_url=share_card.image_url,
                slot_code=share_card.slot_code,
                channel=share_card.channel,
                version=share_card.version,
            ),
        )
    except HTTPException:
        raise
    except ValueError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="系统错误")
    except Exception as exc:
        await db.rollback()
        logger.error(
            "invite_share_get_failed",
            user_id=current_user.id,
            error=str(exc),
            exc_info=True,
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="系统错误")


@router.post("/intake", response_model=InvitationIntakeResponse)
async def intake_invitation_code(
    payload: InvitationIntakeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvitationIntakeResponse:
    """Intake invitation text/link input and return one recognized valid invite code."""
    result = await orchestrate_invitation_intake(
        db,
        mode="auth",
        source=payload.source,
        trigger=payload.trigger,
        raw_text=payload.raw_text,
        invite_code=payload.invite_code,
        actor_user_id=int(current_user.id),
    )
    return InvitationIntakeResponse(
        recognized_code=result.recognized_code,
        valid=result.valid,
        bindable=result.bindable,
    )


@router.post("/resolve", response_model=InvitationResolveResponse)
async def resolve_invite_code(
    payload: InvitationResolveRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvitationResolveResponse:
    """Resolve an invite code and check whether it is bindable for current user."""
    actor_user_id = int(current_user.id)
    await _check_invite_resolve_rate_limit_or_raise(user_id=actor_user_id, db=db)
    code = normalize_invite_code_or_raise(payload.code)
    source = normalize_event_source_or_raise(payload.source)

    code_record = await invite_code_crud.get_active_by_code(db, code=code)
    if code_record is None:
        return InvitationResolveResponse(valid=False, code_type=None, bindable=False)

    inviter_user_id = int(code_record.owner_user_id)
    bindable = await _is_bindable(
        db,
        invitee_user=current_user,
        inviter_user_id=inviter_user_id,
    )

    try:
        await invite_event_crud.create_event(
            db,
            event_type=int(InviteEventType.RESOLVE_VALID),
            actor_user_id=actor_user_id,
            invite_code_id=int(code_record.id),
            event_source=source,
            code_snapshot=code,
            event_payload=None,
        )
    except Exception as exc:
        await db.rollback()
        logger.warning(
            "invite_resolve_event_write_failed",
            user_id=actor_user_id,
            code=code,
            error=str(exc),
        )

    return InvitationResolveResponse(
        valid=True,
        code_type=InviteResolveCodeType.USER,
        bindable=bindable,
    )


@router.post("/bind", response_model=InvitationBindResponse)
async def bind_invite_code(
    payload: InvitationBindRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvitationBindResponse:
    """Bind user invite code and apply invitee reward."""
    actor_user_id = int(current_user.id)
    await _check_invite_bind_rate_limit_or_raise(user_id=actor_user_id, db=db)
    code = normalize_invite_code_or_raise(payload.code)
    source = normalize_event_source_or_raise(payload.source)

    try:
        preview_code_record = await invite_code_crud.get_active_by_code(
            db, code=code, for_update=False
        )
        if preview_code_record is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="邀请码无效")

        preview_inviter_user_id = int(preview_code_record.owner_user_id)
        await _lock_users_in_order(db, user_ids=[actor_user_id, preview_inviter_user_id])

        existing = await invite_binding_crud.get_by_invitee_user_id(
            db,
            invitee_user_id=actor_user_id,
        )
        if existing is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="已绑定邀请码")

        code_record = await invite_code_crud.get_active_by_code(db, code=code, for_update=True)
        if code_record is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="邀请码无效")
        inviter_user_id = int(code_record.owner_user_id)

        policy = await _get_inviter_reward_policy(db)
        if policy.max_invite_count is not None:
            inviter_success_invite_count = (
                await invite_binding_crud.count_success_by_inviter_user_id(
                    db,
                    inviter_user_id=inviter_user_id,
                )
            )
            if inviter_success_invite_count >= policy.max_invite_count:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=INVITE_CAP_REACHED_ERROR,
                )

        if inviter_user_id == actor_user_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="邀请码无效")
        if await invite_binding_crud.is_inviter_of(
            db,
            inviter_user_id=actor_user_id,
            invitee_user_id=inviter_user_id,
        ):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="邀请码无效")

        binding = await invite_binding_crud.create_binding(
            db,
            invitee_user_id=actor_user_id,
            invite_code_id=int(code_record.id),
            code_snapshot=code,
            inviter_user_id_snapshot=inviter_user_id,
        )

        invitee_reward = await apply_growth_rewards(
            db,
            trigger_event=int(GrowthRewardTriggerEvent.INVITE_BIND_SUCCESS),
            target_role=int(GrowthRewardTargetRole.INVITEE),
            actor_user_id=actor_user_id,
            source_id=int(binding.id),
            idempotency_scope="invite_bind",
            event_payload={"binding_id": int(binding.id), "invite_code_id": int(code_record.id)},
        )
        if not bool(current_user.needs_profile_setup):
            await apply_growth_rewards(
                db,
                trigger_event=int(GrowthRewardTriggerEvent.INVITEE_SETUP_COMPLETED),
                target_role=int(GrowthRewardTargetRole.INVITER),
                actor_user_id=inviter_user_id,
                source_id=int(binding.id),
                idempotency_scope=f"invitee_setup:{actor_user_id}",
                event_payload={"invitee_user_id": actor_user_id, "binding_id": int(binding.id)},
            )

        await invite_event_crud.create_event(
            db,
            event_type=int(InviteEventType.BIND_SUCCESS),
            actor_user_id=actor_user_id,
            invite_code_id=int(code_record.id),
            event_source=source,
            code_snapshot=code,
            event_payload={"code_type": InviteResolveCodeType.USER.value},
        )
        if not await invite_event_crud.exists_open_event(
            db,
            actor_user_id=actor_user_id,
            invite_code_id=int(code_record.id),
        ):
            await invite_event_crud.create_event(
                db,
                event_type=int(InviteEventType.OPEN),
                actor_user_id=actor_user_id,
                invite_code_id=int(code_record.id),
                event_source=source,
                code_snapshot=code,
                event_payload={"trigger": "bind_backfill"},
            )

        return InvitationBindResponse(
            code_type=InviteResolveCodeType.USER,
            reward_contact_limit=invitee_reward.total_ai_contact_limit_delta,
        )

    except HTTPException:
        raise
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="已绑定邀请码")
    except Exception as exc:
        await db.rollback()
        logger.error(
            "invite_code_bind_failed",
            user_id=actor_user_id,
            error=str(exc),
            exc_info=True,
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="系统错误")


@router.post("/events", response_model=InvitationEventTrackResponse)
async def track_invitation_event(
    payload: InvitationEventTrackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvitationEventTrackResponse:
    """Track invitation events from client pages."""
    actor_user_id = int(current_user.id)
    source = normalize_event_source_or_raise(payload.source)
    event_type = _event_type_to_code(payload.event_type)
    normalized_code: str | None = None
    invite_code_id: int | None = None
    if payload.code is not None:
        normalized_code = normalize_invite_code_or_raise(payload.code)
        code_record = await invite_code_crud.get_by_code(db, code=normalized_code)
        if code_record is not None:
            invite_code_id = int(code_record.id)

    try:
        await invite_event_crud.create_event(
            db,
            event_type=int(event_type),
            actor_user_id=actor_user_id,
            invite_code_id=invite_code_id,
            event_source=source,
            code_snapshot=normalized_code,
            event_payload=payload.payload,
        )
        return InvitationEventTrackResponse(accepted=True)
    except HTTPException:
        raise
    except Exception as exc:
        await db.rollback()
        logger.error(
            "invite_event_track_failed",
            user_id=actor_user_id,
            event_type=payload.event_type,
            error=str(exc),
            exc_info=True,
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="系统错误")
