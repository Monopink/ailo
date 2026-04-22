"""Public invitation intake endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.invitation import (
    InvitationIntakeRequest,
    InvitationPublicIntakeResponse,
)
from app.services.invitation.intake_orchestrator import orchestrate_invitation_intake
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/public/invitations", tags=["Public Invitations"])


@router.post("/intake", response_model=InvitationPublicIntakeResponse)
async def intake_public_invitation_code(
    payload: InvitationIntakeRequest,
    db: AsyncSession = Depends(get_db),
) -> InvitationPublicIntakeResponse:
    """Intake public invitation text/link input and return one recognized valid invite code."""
    result = await orchestrate_invitation_intake(
        db,
        mode="public",
        source=payload.source,
        trigger=payload.trigger,
        raw_text=payload.raw_text,
        invite_code=payload.invite_code,
        actor_user_id=None,
    )
    return InvitationPublicIntakeResponse(
        recognized_code=result.recognized_code,
        valid=result.valid,
    )
