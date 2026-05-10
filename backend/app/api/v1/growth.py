"""Growth attribution and redeem code API endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.crud.campaign import campaign as campaign_crud
from app.crud.campaign import campaign_attribution as campaign_attribution_crud
from app.crud.redeem import redeem_batch_user_counter as redeem_batch_user_counter_crud
from app.crud.redeem import redeem_code as redeem_code_crud
from app.crud.redeem import redeem_code_batch as redeem_code_batch_crud
from app.crud.redeem import redeem_code_claim as redeem_code_claim_crud
from app.enums.growth import GrowthRewardTargetRole, GrowthRewardTriggerEvent
from app.enums.redeem import RedeemCodeBatchStatus, RedeemCodeMode
from app.models.user import User
from app.schemas.growth import (
    GrowthAttributionTrackRequest,
    GrowthAttributionTrackResponse,
    RedeemCodeClaimRequest,
    RedeemCodeClaimResponse,
)
from app.services.growth.reward_service import apply_growth_rewards
from app.utils.logging import get_logger

logger = get_logger(__name__)

growth_router = APIRouter(prefix="/growth", tags=["Growth"])
redeem_router = APIRouter(prefix="/redeem-codes", tags=["Redeem Codes"])
GROWTH_CODE_MAX_LENGTH = 32
ATTRIBUTION_SOURCE_MAX_LENGTH = 32


def _normalize_campaign_code(raw: str) -> str:
    value = raw.strip().upper()
    if value == "" or len(value) > GROWTH_CODE_MAX_LENGTH:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请求参数错误")
    return value


def _normalize_redeem_code(raw: str) -> str:
    value = raw.strip().upper()
    if value == "" or len(value) > GROWTH_CODE_MAX_LENGTH:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请求参数错误")
    return value


def _normalize_attribution_source(raw: str) -> str:
    value = raw.strip().lower()
    if value == "" or len(value) > ATTRIBUTION_SOURCE_MAX_LENGTH:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请求参数错误")
    compact = value.replace("_", "").replace("-", "")
    if not compact.isascii() or not compact.isalnum():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请求参数错误")
    return value


@growth_router.post("/attributions/track", response_model=GrowthAttributionTrackResponse)
async def track_growth_attribution(
    payload: GrowthAttributionTrackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GrowthAttributionTrackResponse:
    """Track first-touch campaign attribution and apply attribution rewards."""
    actor_user_id = int(current_user.id)
    campaign_code = _normalize_campaign_code(payload.campaign_code)
    attribution_source = _normalize_attribution_source(payload.source)
    now = datetime.now(UTC)
    try:
        existing = await campaign_attribution_crud.get_by_user_id(
            db, user_id=actor_user_id, for_update=False
        )
        if existing is not None:
            return GrowthAttributionTrackResponse(accepted=True, attributed=False)

        campaign = await campaign_crud.get_active_by_code(
            db, campaign_code=campaign_code, at=now, for_update=False
        )
        if campaign is None:
            return GrowthAttributionTrackResponse(accepted=True, attributed=False)

        attribution = await campaign_attribution_crud.create_attribution(
            db,
            user_id=actor_user_id,
            campaign_id=int(campaign.id),
            attribution_source=attribution_source,
            attributed_at=now,
            event_payload=payload.payload,
        )

        await apply_growth_rewards(
            db,
            trigger_event=int(GrowthRewardTriggerEvent.CAMPAIGN_ATTRIBUTION_FIRST_TOUCH),
            target_role=int(GrowthRewardTargetRole.ACTOR),
            actor_user_id=actor_user_id,
            source_id=int(attribution.id),
            idempotency_scope="campaign_attribution",
            campaign_id=int(campaign.id),
            event_payload={
                "campaign_code": campaign_code,
                "source": attribution_source,
            },
            occurred_at=now,
        )
        return GrowthAttributionTrackResponse(accepted=True, attributed=True)
    except IntegrityError:
        await db.rollback()
        return GrowthAttributionTrackResponse(accepted=True, attributed=False)
    except HTTPException:
        raise
    except Exception as exc:
        await db.rollback()
        logger.error(
            "growth_attribution_track_failed",
            user_id=actor_user_id,
            campaign_code=campaign_code,
            error=str(exc),
            exc_info=True,
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="系统错误")


@redeem_router.post("/claim", response_model=RedeemCodeClaimResponse)
async def claim_redeem_code(
    payload: RedeemCodeClaimRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RedeemCodeClaimResponse:
    """Claim one redeem code and apply configured rewards."""
    actor_user_id = int(current_user.id)
    code = _normalize_redeem_code(payload.code)
    now = datetime.now(UTC)
    try:
        redeem = await redeem_code_crud.get_active_by_code(db, code=code, at=now, for_update=True)
        if redeem is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="兑换码无效")

        batch = await redeem_code_batch_crud.get_by_id(
            db, batch_id=int(redeem.batch_id), for_update=False
        )
        if batch is None or int(batch.status) != int(RedeemCodeBatchStatus.ACTIVE):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="兑换码无效")
        if batch.starts_at is not None and batch.starts_at > now:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="兑换码无效")
        if batch.ends_at is not None and batch.ends_at <= now:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="兑换码无效")

        already_claimed = await redeem_code_claim_crud.get_by_user_and_code(
            db,
            user_id=actor_user_id,
            redeem_code_id=int(redeem.id),
        )
        if already_claimed is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="兑换码已领取")

        max_claims_total = (
            int(redeem.max_claims_total) if redeem.max_claims_total is not None else None
        )

        counter_value = await redeem_batch_user_counter_crud.increment_with_cap(
            db,
            batch_id=int(batch.id),
            user_id=actor_user_id,
            max_claims_per_user=int(batch.max_claims_per_user),
        )
        if counter_value is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="已达到领取上限")

        code_incremented = await redeem_code_crud.increment_claimed_total_if_available(
            db,
            redeem_code_id=int(redeem.id),
            at=now,
            max_claims_total=max_claims_total,
            enforce_one_time=int(batch.mode) == int(RedeemCodeMode.ONE_TIME),
        )
        if not code_incremented:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="兑换码已被领完")

        budget_incremented = await redeem_code_batch_crud.increment_budget_used_if_available(
            db,
            batch_id=int(batch.id),
            at=now,
        )
        if not budget_incremented:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="活动预算已用尽")

        claim = await redeem_code_claim_crud.create_claim(
            db,
            user_id=actor_user_id,
            redeem_code_id=int(redeem.id),
            batch_id=int(batch.id),
            code_snapshot=code,
            idempotency_key=f"redeem_claim:{actor_user_id}:{int(redeem.id)}",
            event_payload={"batch_code": batch.batch_code},
        )

        reward = await apply_growth_rewards(
            db,
            trigger_event=int(GrowthRewardTriggerEvent.REDEEM_CODE_CLAIM_SUCCESS),
            target_role=int(GrowthRewardTargetRole.ACTOR),
            actor_user_id=actor_user_id,
            source_id=int(claim.id),
            idempotency_scope="redeem_claim",
            redeem_batch_id=int(batch.id),
            event_payload={"redeem_code_id": int(redeem.id), "batch_code": batch.batch_code},
            occurred_at=now,
        )
        return RedeemCodeClaimResponse(
            claimed=True,
            reward_contact_limit=reward.total_ai_contact_limit_delta,
        )
    except HTTPException:
        raise
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="兑换码已领取")
    except Exception as exc:
        await db.rollback()
        logger.error(
            "redeem_code_claim_failed",
            user_id=actor_user_id,
            code=code,
            error=str(exc),
            exc_info=True,
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="系统错误")
