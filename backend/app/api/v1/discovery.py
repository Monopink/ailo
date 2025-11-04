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
from schemas.discovery import SquareContactListResponse, StrangerProfileResponse
from services.discovery import service as discovery_service
from enums import AIProfileCategory, PROFILE_CATEGORY_API_TO_DB
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
    category: Optional[int] = Query(None, ge=1, le=5, description="Category filter (1-5)"),
    force_refresh: bool = Query(False, description="Force refresh (skip rate limit)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SquareContactListResponse:
    """Get square page random contacts."""
    try:
        # Validate and convert category (API integer -> DB string) using Profile category mapping
        category_db = None
        if category is not None:
            try:
                api_enum = AIProfileCategory(category)
                category_db = PROFILE_CATEGORY_API_TO_DB[api_enum]
            except ValueError:
                logger.warning("invalid_category", user_qiao_id=current_user.qiao_id, category=category)
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无效的分类参数")

        return await discovery_service.get_square_contacts(
            db=db, user_qiao_id=current_user.qiao_id, category=category_db, force_refresh=force_refresh
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


@router.get(
    "/profile/{qiao_id}",
    response_model=StrangerProfileResponse,
    summary="Get stranger profile",
    description="Get public profile of a stranger (no authentication required)",
)
async def get_stranger_profile(
    qiao_id: str,
    db: AsyncSession = Depends(get_db),
) -> StrangerProfileResponse:
    """Get stranger profile by qiao_id.

    This endpoint is public and does not require authentication.
    It returns basic profile information from ai_profile_templates.
    """
    try:
        profile = await discovery_service.get_stranger_profile(db=db, qiao_id=qiao_id)

        if not profile:
            logger.warning("stranger_profile_not_found", qiao_id=qiao_id)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

        return profile
    except HTTPException:
        raise
    except Exception as e:
        logger.error("stranger_profile_error", qiao_id=qiao_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="获取用户信息失败，请稍后再试"
        )
