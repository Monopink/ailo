"""Discovery API endpoints.

This module contains API endpoints for discovery page operations.
"""

import re

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_current_user_optional
from app.core.database import get_db
from app.models.user import User
from app.schemas.discovery import (
    SquareCategoryListResponse,
    SquareContactListResponse,
    StrangerProfileResponse,
)
from app.services.discovery import service as discovery_service
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/discovery", tags=["Discovery"])

_CATEGORY_KEY_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _is_valid_category_key(value: str) -> bool:
    return bool(_CATEGORY_KEY_PATTERN.fullmatch(value))


@router.get(
    "/square-categories",
    response_model=SquareCategoryListResponse,
    summary="Get square categories",
    description="Get active square categories for entry and tabs",
)
async def get_square_categories(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SquareCategoryListResponse:
    """Get active square categories."""
    try:
        response = await discovery_service.get_square_categories(
            db=db,
            current_user=current_user,
        )
        logger.info(
            "square_categories_retrieved",
            user_qiao_id=current_user.qiao_id,
            count=len(response.items),
        )
        return response
    except Exception as exc:
        logger.error(
            "square_categories_error",
            user_qiao_id=current_user.qiao_id,
            error=str(exc),
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="系统错误")


@router.get(
    "/square",
    response_model=SquareContactListResponse,
    summary="Get square contacts feed",
    description="Get AI contacts for square page with cursor pagination support",
)
async def get_square_contacts(
    category_key: str = Query(..., description="Category key (kebab-case)"),
    cursor: str | None = Query(None, description="Opaque cursor for loading next page"),
    page_size: int | None = Query(
        None, ge=1, le=50, description="Items per page (default from config, max 50)"
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SquareContactListResponse:
    """Get square page contacts with pagination."""
    if not _is_valid_category_key(category_key):
        logger.warning(
            "invalid_category_key_format",
            user_qiao_id=current_user.qiao_id,
            category_key=category_key,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无效的分类参数")

    try:
        return await discovery_service.get_square_contacts(
            db=db,
            current_user=current_user,
            user_qiao_id=current_user.qiao_id,
            category_key=category_key,
            cursor=cursor,
            page_size=page_size,
        )
    except ValueError as exc:
        error_msg = str(exc)
        if error_msg.startswith("RATE_LIMIT:"):
            logger.warning(
                "square_rate_limit",
                user_qiao_id=current_user.qiao_id,
                category_key=category_key,
                error=error_msg,
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="请求过于频繁"
            )
        if error_msg == "INVALID_CATEGORY_KEY":
            logger.warning(
                "square_category_not_available",
                user_qiao_id=current_user.qiao_id,
                category_key=category_key,
            )
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无效的分类参数")
        if error_msg == "INVALID_CURSOR":
            logger.warning(
                "square_invalid_cursor",
                user_qiao_id=current_user.qiao_id,
                category_key=category_key,
                cursor=cursor,
            )
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无效的游标参数")
        logger.error(
            "square_validation_error",
            user_qiao_id=current_user.qiao_id,
            category_key=category_key,
            error=error_msg,
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="系统错误")
    except Exception as exc:
        logger.error(
            "square_contacts_error",
            user_qiao_id=current_user.qiao_id,
            category_key=category_key,
            error=str(exc),
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="系统错误")


@router.get(
    "/profile/{qiao_id}",
    response_model=StrangerProfileResponse,
    summary="Get stranger profile",
    description="Get public profile of a stranger (no authentication required)",
)
async def get_stranger_profile(
    qiao_id: str,
    category_key: str | None = Query(None, description="Source category key (optional)"),
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> StrangerProfileResponse:
    """Get stranger profile by qiao_id."""
    if category_key is not None and not _is_valid_category_key(category_key):
        logger.warning(
            "invalid_profile_category_key_format",
            qiao_id=qiao_id,
            category_key=category_key,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请求参数错误")

    try:
        profile = await discovery_service.get_stranger_profile(
            db=db,
            qiao_id=qiao_id,
            current_user=current_user,
            category_key=category_key,
        )
        if not profile:
            logger.warning("stranger_profile_not_found", qiao_id=qiao_id)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
        return profile
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "stranger_profile_error",
            qiao_id=qiao_id,
            category_key=category_key,
            error=str(exc),
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="系统错误")
