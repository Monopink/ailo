"""
Discovery API endpoints.

This module contains API endpoints for discovery page operations.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from api.deps import get_current_user
from models.user import User
from schemas.discovery import SquareContactListResponse
from services.discovery import service as discovery_service
from utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/discovery", tags=["Discovery"])


@router.get(
    "/square",
    response_model=SquareContactListResponse,
    summary="Get square random contacts",
    description="Get random AI contacts for square page with rate limiting",
)
async def get_square_contacts(
    category: Optional[str] = Query(None, description="Category filter"),
    force_refresh: bool = Query(False, description="Force refresh (skip rate limit)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SquareContactListResponse:
    """Get square page random contacts."""
    try:
        return await discovery_service.get_square_contacts(
            db=db, user_qiao_id=current_user.qiao_id, category=category, force_refresh=force_refresh
        )
    except ValueError as e:
        # Rate limit error
        error_msg = str(e)
        if "Refresh too frequent" in error_msg:
            logger.warning("square_refresh_rate_limit", user_qiao_id=current_user.qiao_id, error=error_msg)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="刷新过于频繁，请稍后再试"
            )
        else:
            logger.error(
                "square_contacts_validation_error", user_qiao_id=current_user.qiao_id, error=error_msg
            )
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请求参数错误")
    except Exception as e:
        logger.error("square_contacts_error", user_qiao_id=current_user.qiao_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="获取内容失败，请稍后再试"
        )
