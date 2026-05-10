"""Invitation API endpoints."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.crud.growth_reward import growth_reward_rule as growth_reward_rule_crud
from app.crud.invite import invite_binding as invite_binding_crud
from app.crud.invite import invite_code as invite_code_crud
from app.crud.invite import invite_event as invite_event_crud
from app.enums.growth import GrowthRewardTargetRole, GrowthRewardTriggerEvent
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
    InvitationPolicyResponse,
    InvitationResolveRequest,
    InvitationResolveResponse,
    InvitationShareCardResponse,
    InvitationShareCommandResponse,
    InvitationStatsResponse,
)
from app.services.entitlement.service import ENTITLEMENT_SOURCE_INVITE_BIND_INVITER
from app.services.growth.invitation_policy import get_invitation_policy_rules
from app.services.growth.reward_service import apply_growth_rewards
from app.services.invitation.bindability import is_invite_code_bindable
from app.services.invitation.intake import (
    normalize_event_source_or_raise,
    normalize_invite_code_or_raise,
)
from app.services.invitation.intake_orchestrator import orchestrate_invitation_intake
from app.services.invitation.share_card import resolve_invite_share_card
from app.services.review_scope_policy import (
    is_invitation_capability_allowed,
    resolve_effective_review_scope,
)
from app.services.security.rate_limiter import check_rate_limit
from app.services.system_config import get_config_str_list
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/invitations", tags=["Invitations"])

USER_INVITE_CODE_LENGTH = 6
USER_INVITE_CODE_CHARSET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
INVITE_SHARE_CODE_PLACEHOLDER = "{{code}}"
INVITE_SHARE_LINK_PLACEHOLDER = "{{link}}"
INVITE_CAP_REACHED_ERROR = "邀请人数已达上限"
INVITE_SHARE_COMMAND_TEXTS_CONFIG_KEY = "invite_share_command_texts"
INVITE_SHARE_CARD_TITLES_CONFIG_KEY = "invite_share_card_titles"


def _ensure_invitation_capability_or_raise(current_user: User) -> None:
    if is_invitation_capability_allowed(current_user):
        return
    logger.info(
        "invitation_capability_blocked",
        user_id=int(current_user.id),
        user_qiao_id=current_user.qiao_id,
        review_scope=resolve_effective_review_scope(current_user).name,
    )
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前账号暂不可用该功能")


def _generate_user_invite_code() -> str:
    return "".join(secrets.choice(USER_INVITE_CODE_CHARSET) for _ in range(USER_INVITE_CODE_LENGTH))


def _pick_random_text(candidates: list[str]) -> str:
    """Pick one candidate string for share rendering."""
    if len(candidates) == 0:
        raise ValueError("empty_share_text_candidates")
    return secrets.choice(candidates)


def _render_invite_share_template(template: str, *, code: str, link: str) -> str:
    """Render invite placeholders in one template string."""
    return template.replace(INVITE_SHARE_CODE_PLACEHOLDER, code).replace(
        INVITE_SHARE_LINK_PLACEHOLDER, link
    )


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


class _InviterRewardPolicy:
    def __init__(
        self,
        *,
        reward_contact_delta: int,
        max_rewards_per_actor: int | None,
        rule_id: int,
    ) -> None:
        self.reward_contact_delta = reward_contact_delta
        self.max_rewards_per_actor = max_rewards_per_actor
        self.rule_id = rule_id


async def _get_inviter_reward_policy(db: AsyncSession) -> _InviterRewardPolicy:
    try:
        policy_rules = await get_invitation_policy_rules(db, for_update=False)
    except ValueError:
        logger.error("invite_stats_rule_invalid")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="系统错误")
    selected_rule = policy_rules.inviter_rule
    reward_contact_delta = int(selected_rule.delta_granted)
    if reward_contact_delta < 0:
        logger.error(
            "invite_stats_rule_delta_invalid",
            rule_id=int(selected_rule.id),
            delta=reward_contact_delta,
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="系统错误")
    max_rewards_per_actor = (
        int(selected_rule.max_rewards_per_actor)
        if selected_rule.max_rewards_per_actor is not None
        else None
    )
    if max_rewards_per_actor is not None and max_rewards_per_actor < 1:
        logger.error(
            "invite_stats_rule_cap_invalid",
            rule_id=int(selected_rule.id),
            max_rewards_per_actor=max_rewards_per_actor,
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="系统错误")

    return _InviterRewardPolicy(
        reward_contact_delta=reward_contact_delta,
        max_rewards_per_actor=max_rewards_per_actor,
        rule_id=int(selected_rule.id),
    )


@router.get("/binding-status", response_model=InvitationBindingStatusResponse)
async def get_invitation_binding_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvitationBindingStatusResponse:
    """Get whether current user has already bound an invite code."""
    _ensure_invitation_capability_or_raise(current_user)
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
    _ensure_invitation_capability_or_raise(current_user)
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


@router.get("/policy", response_model=InvitationPolicyResponse)
async def get_invitation_policy(
    _current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvitationPolicyResponse:
    """Get unified invitation policy for client pages."""
    _ensure_invitation_capability_or_raise(_current_user)
    try:
        policy_rules = await get_invitation_policy_rules(db, for_update=False)
        invitee_rule = policy_rules.invitee_rule
        inviter_rule = policy_rules.inviter_rule
        inviter_max_rewards_per_actor = (
            int(inviter_rule.max_rewards_per_actor)
            if inviter_rule.max_rewards_per_actor is not None
            else None
        )
        return InvitationPolicyResponse(
            invitee_reward_contact_delta=int(invitee_rule.delta_granted),
            inviter_reward_contact_delta=int(inviter_rule.delta_granted),
            inviter_max_rewards_per_actor=inviter_max_rewards_per_actor,
        )
    except ValueError:
        logger.error("invite_policy_rule_invalid")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="系统错误")
    except HTTPException:
        raise
    except Exception as exc:
        await db.rollback()
        logger.error(
            "invite_policy_get_failed",
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
    _ensure_invitation_capability_or_raise(current_user)
    try:
        policy = await _get_inviter_reward_policy(db)
        success_invite_count = await invite_binding_crud.count_success_by_inviter_user_id(
            db,
            inviter_user_id=int(current_user.id),
        )
        (
            _apply_count,
            apply_total,
            ledger_total,
            mismatch_count,
        ) = await growth_reward_rule_crud.get_actor_applied_reward_truth(
            db,
            rule_id=policy.rule_id,
            actor_user_id=int(current_user.id),
            source_type=ENTITLEMENT_SOURCE_INVITE_BIND_INVITER,
        )
        if mismatch_count > 0 or apply_total != ledger_total:
            logger.error(
                "invite_stats_reward_truth_mismatch",
                actor_user_id=int(current_user.id),
                rule_id=policy.rule_id,
                apply_total=apply_total,
                ledger_total=ledger_total,
                mismatch_count=mismatch_count,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="系统错误"
            )
        preview_bind_count = (
            min(success_invite_count, policy.max_rewards_per_actor)
            if policy.max_rewards_per_actor is not None
            else success_invite_count
        )
        preview_total = preview_bind_count * policy.reward_contact_delta
        return InvitationStatsResponse(
            inviter_success_bind_count=success_invite_count,
            inviter_reward_contact_limit_actual_total=apply_total,
            inviter_reward_contact_limit_preview_total=preview_total,
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


@router.get("/share-command", response_model=InvitationShareCommandResponse)
async def get_invitation_share_command(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvitationShareCommandResponse:
    """Get invite command payload for copy/share text."""
    _ensure_invitation_capability_or_raise(current_user)
    try:
        code = await _get_or_create_user_invite_code(db, user_id=current_user.id)
        link = f"{str(request.base_url).rstrip('/')}/i/{code}"

        share_command_templates = await get_config_str_list(
            db,
            key=INVITE_SHARE_COMMAND_TEXTS_CONFIG_KEY,
            required=True,
        )

        selected_template = _pick_random_text(share_command_templates)
        text = _render_invite_share_template(selected_template, code=code, link=link)

        return InvitationShareCommandResponse(
            code=code,
            text=text,
            link=link,
        )
    except HTTPException:
        raise
    except ValueError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="系统错误")
    except Exception as exc:
        await db.rollback()
        logger.error(
            "invite_share_command_get_failed",
            user_id=current_user.id,
            error=str(exc),
            exc_info=True,
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="系统错误")


@router.get("/share-card", response_model=InvitationShareCardResponse)
async def get_invitation_share_card(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvitationShareCardResponse:
    """Get mini-program share card payload."""
    _ensure_invitation_capability_or_raise(current_user)
    try:
        code = await _get_or_create_user_invite_code(db, user_id=current_user.id)

        share_card_title_templates = await get_config_str_list(
            db,
            key=INVITE_SHARE_CARD_TITLES_CONFIG_KEY,
            required=True,
        )

        share_card_title = _pick_random_text(share_card_title_templates)

        share_card = resolve_invite_share_card(code=code)

        return InvitationShareCardResponse(
            code=code,
            title=share_card_title,
            path=share_card.path,
            image_url=share_card.image_url,
        )
    except HTTPException:
        raise
    except ValueError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="系统错误")
    except Exception as exc:
        await db.rollback()
        logger.error(
            "invite_share_card_get_failed",
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
    _ensure_invitation_capability_or_raise(current_user)
    result = await orchestrate_invitation_intake(
        db,
        mode="auth",
        source=payload.source,
        trigger=payload.trigger,
        raw_text=payload.raw_text,
        invite_code=payload.invite_code,
        actor_user_id=int(current_user.id),
        reviewer_flag_snapshot=1 if payload.segment_type == 1 else 0,
        runtime_observation_id=payload.runtime_observation_id,
        client_user_agent=payload.client_user_agent or "",
        client_device_id=payload.device_id or "",
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
    _ensure_invitation_capability_or_raise(current_user)
    actor_user_id = int(current_user.id)
    await _check_invite_resolve_rate_limit_or_raise(user_id=actor_user_id, db=db)
    code = normalize_invite_code_or_raise(payload.code)
    source = normalize_event_source_or_raise(payload.source)

    code_record = await invite_code_crud.get_active_by_code(db, code=code)
    if code_record is None:
        return InvitationResolveResponse(valid=False, code_type=None, bindable=False)

    inviter_user_id = int(code_record.owner_user_id)
    bindable = await is_invite_code_bindable(
        db,
        invitee_user_id=int(current_user.id),
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
    """Bind user invite code and apply invite rewards."""
    _ensure_invitation_capability_or_raise(current_user)
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
        if policy.max_rewards_per_actor is not None:
            inviter_success_invite_count = (
                await invite_binding_crud.count_success_by_inviter_user_id(
                    db,
                    inviter_user_id=inviter_user_id,
                )
            )
            if inviter_success_invite_count >= policy.max_rewards_per_actor:
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
            idempotency_scope="invite_bind_invitee",
            event_payload={"binding_id": int(binding.id), "invite_code_id": int(code_record.id)},
        )
        await apply_growth_rewards(
            db,
            trigger_event=int(GrowthRewardTriggerEvent.INVITE_BIND_SUCCESS),
            target_role=int(GrowthRewardTargetRole.INVITER),
            actor_user_id=inviter_user_id,
            source_id=int(binding.id),
            idempotency_scope="invite_bind_inviter",
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
    _ensure_invitation_capability_or_raise(current_user)
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
