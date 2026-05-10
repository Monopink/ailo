"""WebSocket session ticket issue/verify helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt

from app.core.config import get_settings
from app.models.user import User

_WS_SESSION_TICKET_SCOPE = "ws_session_ticket"


@dataclass(slots=True)
class WSSessionTicketClaims:
    """Validated websocket session ticket claims."""

    user_id: int
    user_qiao_id: str
    device_id: UUID
    issued_at_ms: int
    expires_at_ms: int


def issue_ws_session_ticket(
    *,
    user: User,
    device_id: UUID,
    ttl_seconds: int,
) -> tuple[str, WSSessionTicketClaims]:
    """Issue a short-lived websocket session ticket."""
    if ttl_seconds <= 0:
        raise ValueError("ttl_seconds must be positive")

    now = datetime.now(UTC)
    exp = now + timedelta(seconds=ttl_seconds)
    issued_at_seconds = int(now.timestamp())
    expires_at_seconds = int(exp.timestamp())
    issued_at_ms = issued_at_seconds * 1000
    expires_at_ms = expires_at_seconds * 1000

    payload = {
        "scope": _WS_SESSION_TICKET_SCOPE,
        "sub": str(user.qiao_id),
        "uid": int(user.id),
        "did": str(device_id),
        "iat": issued_at_seconds,
        "exp": expires_at_seconds,
        "jti": uuid4().hex,
    }

    settings = get_settings()
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    claims = WSSessionTicketClaims(
        user_id=int(user.id),
        user_qiao_id=str(user.qiao_id),
        device_id=device_id,
        issued_at_ms=issued_at_ms,
        expires_at_ms=expires_at_ms,
    )
    return token, claims


def _build_claims_from_payload(payload: object) -> WSSessionTicketClaims | None:
    if not isinstance(payload, dict) or payload.get("scope") != _WS_SESSION_TICKET_SCOPE:
        return None

    user_qiao_id = payload.get("sub")
    user_id_raw = payload.get("uid")
    device_id_raw = payload.get("did")
    iat_raw = payload.get("iat")
    exp_raw = payload.get("exp")

    if (
        not isinstance(user_qiao_id, str)
        or not user_qiao_id
        or not isinstance(user_id_raw, int)
        or user_id_raw <= 0
        or not isinstance(device_id_raw, str)
        or not device_id_raw
        or not isinstance(iat_raw, int)
        or iat_raw <= 0
        or not isinstance(exp_raw, int)
        or exp_raw <= 0
    ):
        return None

    device_id: UUID | None = None
    try:
        device_id = UUID(device_id_raw)
    except ValueError:
        device_id = None
    if device_id is None:
        return None

    return WSSessionTicketClaims(
        user_id=user_id_raw,
        user_qiao_id=user_qiao_id,
        device_id=device_id,
        issued_at_ms=iat_raw * 1000,
        expires_at_ms=exp_raw * 1000,
    )


def verify_ws_session_ticket(ticket: str) -> WSSessionTicketClaims | None:
    """Verify websocket session ticket and return claims."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            ticket,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.InvalidTokenError:
        return None

    return _build_claims_from_payload(payload)
