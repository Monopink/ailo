"""
Discovery service business logic.

This module provides business logic for discovery page operations.
"""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from crud.system import system_configs
from enums import PROFILE_CATEGORY_DB_TO_API
from schemas.discovery import SquareContactResponse, SquareContactListResponse, PaginationInfo, StrangerProfileResponse
from services.discovery import data as discovery_data
from services.security.rate_limiter import check_rate_limit
from utils.logging import get_logger

logger = get_logger(__name__)


async def get_square_contacts(
    db: AsyncSession,
    user_qiao_id: str,
    category: Optional[str] = None,
    page: int = 1,
    page_size: Optional[int] = None,
) -> SquareContactListResponse:
    """
    Get square page contacts with pagination.

    Args:
        db: Database session
        user_qiao_id: Current user's qiao_id
        category: Optional category filter (DB string format)
        page: Page number (1-indexed)
        page_size: Items per page (None = use config default)

    Returns:
        SquareContactListResponse with pagination info

    Raises:
        ValueError: Rate limit exceeded
    """
    try:
        # Load page_size from config if not provided
        if page_size is None:
            page_size = int(
                await system_configs.get_config_value(db, config_key="square_page_size", default_value=20)
            )

        # Check rate limit
        rate_key = f"{user_qiao_id}:{category or 'all'}"
        allowed, error_code, retry_after = await check_rate_limit(
            identifier=rate_key, group="square", db=db
        )

        if not allowed:
            logger.warning(
                "square_rate_limit",
                user_qiao_id=user_qiao_id,
                category=category,
                retry_after=retry_after,
            )
            raise ValueError(f"Request too frequent, wait {retry_after} seconds")

        # Query templates with pagination
        templates, total = await discovery_data.get_random_templates(
            db=db, user_qiao_id=user_qiao_id, category=category, page=page, page_size=page_size
        )

        # Transform to response format
        items = []
        for template in templates:
            api_enum = PROFILE_CATEGORY_DB_TO_API.get(template.category) if template.category else None
            category_api = api_enum.value if api_enum is not None else None

            items.append(
                SquareContactResponse(
                    qiao_id=template.qiao_id,
                    category=category_api,
                    nickname=template.nickname,
                    gender=template.gender,
                    avatar_url=template.avatar_url,
                    bio=template.bio,
                    region=template.region,
                )
            )

        # Build pagination info
        has_more = (page * page_size) < total
        pagination = PaginationInfo(page=page, page_size=page_size, total=total, has_more=has_more)

        logger.info(
            "square_contacts_retrieved",
            user_qiao_id=user_qiao_id,
            count=len(items),
            category=category,
            page=page,
            total=total,
        )

        return SquareContactListResponse(items=items, pagination=pagination)

    except ValueError:
        raise
    except Exception as e:
        logger.error("square_contacts_service_error", user_qiao_id=user_qiao_id, category=category, error=str(e))
        raise RuntimeError(f"Failed to get square contacts: {str(e)}")


async def get_stranger_profile(db: AsyncSession, qiao_id: str) -> Optional[StrangerProfileResponse]:
    """
    Get stranger profile by qiao_id.

    This is a public endpoint that returns basic profile information
    from ai_profile_templates without requiring authentication.

    Args:
        db: Database session
        qiao_id: Profile qiao_id to query

    Returns:
        StrangerProfileResponse or None if not found
    """
    try:
        # Query profile template by qiao_id
        template = await discovery_data.get_template_by_qiao_id(db=db, qiao_id=qiao_id)

        if not template:
            logger.warning("stranger_profile_not_found", qiao_id=qiao_id)
            return None

        # Transform to response format
        # Convert DB string category to API integer (Profile category)
        api_enum = PROFILE_CATEGORY_DB_TO_API.get(template.category) if template.category else None
        category_api = api_enum.value if api_enum is not None else None

        profile = StrangerProfileResponse(
            qiao_id=template.qiao_id,
            nickname=template.nickname,
            gender=template.gender,
            avatar_url=template.avatar_url,
            bio=template.bio,
            region=template.region,
            category=category_api,
        )

        logger.info("stranger_profile_retrieved", qiao_id=qiao_id)
        return profile

    except Exception as e:
        logger.error("stranger_profile_service_error", qiao_id=qiao_id, error=str(e))
        raise RuntimeError(f"Failed to get stranger profile: {str(e)}")
