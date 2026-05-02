"""Public invitation intake endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.invitation import (
    InvitationIntakeRequest,
    InvitationPublicIntakeResponse,
)
from app.services.invitation.intake_orchestrator import orchestrate_invitation_intake
from app.services.security.rate_limiter import check_rate_limit
from app.utils.client_ip import ClientIPResolutionError, get_client_ip
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/public/invitations", tags=["Public Invitations"])


def _safe_client_ip(request: Request) -> str:
    try:
        return get_client_ip(request)
    except ClientIPResolutionError:
        return ""


async def _is_public_intake_rate_limited(
    *,
    request: Request,
    payload: InvitationIntakeRequest,
    db: AsyncSession,
) -> bool:
    client_ip = _safe_client_ip(request)
    identifiers: list[str] = []
    if payload.device_id:
        identifiers.append(f"device:{payload.device_id}")
    if client_ip != "":
        identifiers.append(f"ip:{client_ip}")

    for identifier in identifiers:
        allowed, _error_code, _retry_after = await check_rate_limit(
            identifier,
            "public_invite_intake",
            db,
        )
        if not allowed:
            return True
    return False


@router.post("/intake", response_model=InvitationPublicIntakeResponse)
async def intake_public_invitation_code(
    request: Request,
    payload: InvitationIntakeRequest,
    db: AsyncSession = Depends(get_db),
) -> InvitationPublicIntakeResponse:
    """Intake public invitation text/link input and return one recognized valid invite code."""
    if await _is_public_intake_rate_limited(request=request, payload=payload, db=db):
        return InvitationPublicIntakeResponse(recognized_code=None, valid=False)

    result = await orchestrate_invitation_intake(
        db,
        mode="public",
        source=payload.source,
        trigger=payload.trigger,
        raw_text=payload.raw_text,
        invite_code=payload.invite_code,
        actor_user_id=None,
        reviewer_flag_snapshot=1 if payload.segment_type == 1 else 0,
        runtime_observation_id=payload.runtime_observation_id,
        client_user_agent=payload.client_user_agent or "",
        client_device_id=payload.device_id or "",
    )
    return InvitationPublicIntakeResponse(
        recognized_code=result.recognized_code,
        valid=result.valid,
    )
