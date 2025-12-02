"""
Discovery API endpoints.

This module contains API endpoints for discovery page operations.
"""

from api.deps import get_current_user
from core.database import get_db
from enums import SquareCategory
from fastapi import APIRouter, Depends, HTTPException, Query, status
from models.user import User
from schemas.discovery import SquareContactListResponse, StrangerProfileResponse
from services.discovery import service as discovery_service
from sqlalchemy.ext.asyncio import AsyncSession
from utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/discovery", tags=["Discovery"])


@router.get(
    "/square",
    response_model=SquareContactListResponse,
    summary="Get square contacts with pagination",
    description="Get AI contacts for square page with pagination support",
)
async def get_square_contacts(
    category: int | None = Query(
        None, ge=1, le=5, description="Category filter (1-5, null for all)"
    ),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int | None = Query(
        None, ge=1, le=50, description="Items per page (default from config, max 50)"
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SquareContactListResponse:
    """Get square page contacts with pagination."""
    try:
        # Validate and convert category
        category_enum = None
        if category is not None:
            try:
                category_enum = SquareCategory(category)
            except ValueError:
                logger.warning(
                    "invalid_category", user_qiao_id=current_user.qiao_id, category=category
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="无效的分类参数"
                )

        return await discovery_service.get_square_contacts(
            db=db,
            user_qiao_id=current_user.qiao_id,
            category=category_enum,
            page=page,
            page_size=page_size,
        )
    except ValueError as e:
        error_msg = str(e)
        if "too frequent" in error_msg.lower():
            logger.warning("square_rate_limit", user_qiao_id=current_user.qiao_id, error=error_msg)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="请求过于频繁"
            )
        logger.error("square_validation_error", user_qiao_id=current_user.qiao_id, error=error_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请求参数错误")
    except Exception as e:
        logger.error("square_contacts_error", user_qiao_id=current_user.qiao_id, error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="系统错误")


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
    It returns basic profile information from ai_personas.
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
