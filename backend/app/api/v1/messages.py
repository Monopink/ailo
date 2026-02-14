"""Offline message endpoints."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.message.offline import (
    OfflineMessageAckRequest,
    OfflineMessageAckResponse,
    OfflineMessagesResponse,
)
from app.services.message.offline import ack_offline_message, fetch_offline_messages
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/messages", tags=["Messages"])


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
