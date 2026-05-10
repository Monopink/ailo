"""Offline message endpoints."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.models.user import User
from app.schemas.message.offline import (
    OfflineMessageAckRequest,
    OfflineMessageAckResponse,
    OfflineMessagesResponse,
)
from app.schemas.message.ws_session import (
    MessageWSPresencePayload,
    MessageWSSessionAuth,
    MessageWSSessionBootstrapResponse,
    MessageWSSessionPayload,
    MessageWSSessionTicketRequest,
)
from app.services.message.offline import ack_offline_message, fetch_offline_messages
from app.services.message.websocket import issue_ws_session_ticket
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/messages", tags=["Messages"])


@router.post("/ws-session", response_model=MessageWSSessionBootstrapResponse)
async def issue_ws_session(
    payload: MessageWSSessionTicketRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> MessageWSSessionBootstrapResponse:
    """Issue a short-lived websocket session ticket for realtime auth."""
    try:
        device_uuid = UUID(payload.device_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="参数错误") from exc

    settings = get_settings()
    ttl_seconds = settings.MESSAGE_WS_SESSION_TICKET_TTL_SECONDS
    ws_ticket, claims = issue_ws_session_ticket(
        user=current_user,
        device_id=device_uuid,
        ttl_seconds=ttl_seconds,
    )
    expires_in_ms = max(claims.expires_at_ms - claims.issued_at_ms, 0)
    base_url = str(request.base_url).rstrip("/")
    config_version = f"ws:{current_user.qiao_id}:{device_uuid}:{claims.issued_at_ms}"

    return MessageWSSessionBootstrapResponse(
        config_version=config_version,
        session=MessageWSSessionPayload(
            client_id=str(current_user.qiao_id),
            provider="websocket",
            server_url=base_url,
            session_hint="__ws__",
            auth=MessageWSSessionAuth(
                scheme="ws_ticket",
                version="1",
                ws_ticket=ws_ticket,
                issued_at_ms=claims.issued_at_ms,
                device_id=str(device_uuid),
                expires_in_ms=expires_in_ms,
            ),
        ),
        presence=MessageWSPresencePayload(
            endpoint_id=0,
            lease_ttl_days=0,
            lease_expires_at_ms=0,
        ),
    )


@router.get("/offline", response_model=OfflineMessagesResponse)
async def get_offline_messages(
    device_id: str = Query(..., description="Device/installation UUID"),
    limit: int | None = Query(None, ge=1, le=100, description="Page size"),
    cursor: str | None = Query(None, description="Pagination cursor"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OfflineMessagesResponse:
    """Fetch offline messages for the authenticated user."""
    try:
        messages, next_cursor, has_more, effective_limit = await fetch_offline_messages(
            db=db,
            user=current_user,
            device_id=device_id,
            limit=limit,
            cursor=cursor,
        )
        return OfflineMessagesResponse(
            server_time_ms=int(datetime.now(tz=UTC).timestamp() * 1000),
            limit=effective_limit,
            has_more=has_more,
            next_cursor=next_cursor,
            messages=messages,
        )
    except ValueError as e:
        logger.warning(
            "offline_messages_bad_request",
            user_qiao_id=current_user.qiao_id,
            device_id=device_id,
            error=str(e),
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="参数错误") from e
    except Exception as e:
        logger.error(
            "offline_messages_failed",
            user_qiao_id=current_user.qiao_id,
            device_id=device_id,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="系统错误"
        ) from e


@router.post("/ack", response_model=OfflineMessageAckResponse)
async def ack_offline_messages(
    payload: OfflineMessageAckRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OfflineMessageAckResponse:
    """Acknowledge offline messages."""
    try:
        await ack_offline_message(db=db, user=current_user, payload=payload)
        return OfflineMessageAckResponse(
            success=True,
            server_time_ms=int(datetime.now(tz=UTC).timestamp() * 1000),
        )
    except ValueError as e:
        logger.warning(
            "offline_ack_bad_request",
            user_qiao_id=current_user.qiao_id,
            device_id=payload.device_id,
            error=str(e),
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="参数错误") from e
    except Exception as e:
        logger.error(
            "offline_ack_failed",
            user_qiao_id=current_user.qiao_id,
            device_id=payload.device_id,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="系统错误"
        ) from e
