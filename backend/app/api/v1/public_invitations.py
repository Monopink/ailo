"""Public invitation intake endpoints."""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.enums import DetectionSource
from app.exceptions.error_codes import build_protective_denial_detail
from app.schemas.invitation import (
    InvitationIntakeRequest,
    InvitationPublicIntakeResponse,
)
from app.services.invitation.intake_orchestrator import orchestrate_invitation_intake
from app.services.security import SecurityRequestContext, enforce_attack_scan, is_ip_blocked
from app.services.security.rate_limiter import check_rate_limit
from app.utils.client_ip import ClientIPResolutionError, get_client_ip
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/public/invitations", tags=["Public Invitations"])


def _resolve_client_ip_or_deny(*, request: Request, request_id: str) -> str:
    try:
        return get_client_ip(request)
    except ClientIPResolutionError as exc:
        logger.warning(
            "public_invite_intake_client_ip_resolve_failed",
            request_id=request_id,
            reason=exc.reason,
        )
        raise HTTPException(
            status_code=403,
            detail=build_protective_denial_detail(
                reason="CLIENT_IP_RESOLUTION_FAILED",
                camouflage_message="请求来源受限",
                metadata={"request_id": request_id},
            ),
        ) from exc


def _request_id(request: Request) -> str:
    request_id = getattr(request.state, "request_id", None)
    if isinstance(request_id, str) and request_id:
        return request_id
    header_value = request.headers.get("X-Request-ID") or request.headers.get("x-request-id")
    if isinstance(header_value, str) and header_value.strip():
        request_id = header_value.strip()
    else:
        request_id = f"req_{uuid4().hex[:12]}"
    request.state.request_id = request_id
    return request_id


async def _guard_public_attack(
    *,
    request: Request,
    client_ip: str,
    request_id: str,
    payload: InvitationIntakeRequest,
    db: AsyncSession,
) -> None:
    if await is_ip_blocked(db, client_ip):
        raise HTTPException(
            status_code=403,
            detail=build_protective_denial_detail(
                reason="IP_BLOCKED",
                camouflage_message="请求来源受限",
                metadata={"request_id": request_id},
            ),
        )

    match = await enforce_attack_scan(
        db,
        context=SecurityRequestContext(
            detection_source=DetectionSource.API_PUBLIC_INVITATION,
            request_method=request.method,
            request_path=request.url.path,
            client_ip=client_ip,
            request_id=request_id,
            user_id=None,
            user_qiao_id=None,
        ),
        fields={
            "source": payload.source,
            "trigger": payload.trigger,
            "raw_text": payload.raw_text or "",
            "invite_code": payload.invite_code or "",
            "client_user_agent": payload.client_user_agent or "",
            "device_id": payload.device_id or "",
        },
        extra_evidence={"layer": "public_invitation"},
    )
    if match is not None:
        raise HTTPException(
            status_code=403,
            detail=build_protective_denial_detail(
                reason="ATTACK_DETECTED",
                camouflage_message="请求来源受限",
                risk_rule_id=match.rule_code,
                internal_risk_code=match.rule_code,
                metadata={"rule_code": match.rule_code, "field_name": match.field_name},
            ),
        )


async def _is_public_intake_rate_limited(
    *,
    client_ip: str,
    payload: InvitationIntakeRequest,
    db: AsyncSession,
) -> bool:
    identifiers: list[str] = []
    if payload.device_id:
        identifiers.append(f"device:{payload.device_id}")
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
    request_id = _request_id(request)
    client_ip = _resolve_client_ip_or_deny(request=request, request_id=request_id)
    await _guard_public_attack(
        request=request,
        client_ip=client_ip,
        request_id=request_id,
        payload=payload,
        db=db,
    )
    if await _is_public_intake_rate_limited(client_ip=client_ip, payload=payload, db=db):
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
