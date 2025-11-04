"""
Discovery service business logic.

This module provides business logic for discovery page operations.
"""

from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from crud.system import system_configs
from enums import PROFILE_CATEGORY_DB_TO_API
from schemas.discovery import SquareContactResponse, SquareContactListResponse, StrangerProfileResponse
from services.discovery import data as discovery_data
from services.security.rate_limiter import check_rate_limit
from utils.logging import get_logger

logger = get_logger(__name__)


async def get_square_contacts(
    db: AsyncSession, user_qiao_id: str, category: Optional[str] = None, force_refresh: bool = False
) -> SquareContactListResponse:
    """
    Get square page random contacts.

    Business logic:
    1. Read config: square_recommend_count, square_refresh_interval
    2. Check refresh rate limit (unless force_refresh=True)
    3. Query random templates (via data layer)
    4. Transform to response format
    5. Update refresh cache

    Args:
        db: Database session
        user_qiao_id: Current user's qiao_id
        category: Optional category filter
        force_refresh: Skip rate limit check (for admin/testing)

    Returns:
        SquareContactListResponse

    Raises:
        ValueError: Rate limit exceeded (English message)
    """
    try:
        # Read configuration
        recommend_count = await system_configs.get_config_value(
            db, config_key="square_recommend_count", default_value=10
        )
        recommend_count = int(recommend_count)

        logger.debug("square_config_loaded", recommend_count=recommend_count)

        # Check refresh rate limit using standard rate limiter
        if not force_refresh:
            allowed, error_code, retry_after = await check_rate_limit(
                identifier=user_qiao_id, group="square", db=db
            )

            if not allowed:
                logger.warning(
                    "square_refresh_rate_limit",
                    user_qiao_id=user_qiao_id,
                    error_code=error_code,
                    retry_after=retry_after,
                )
                raise ValueError(f"Refresh too frequent, wait {retry_after} seconds")

        # Query random templates
        templates = await discovery_data.get_random_templates(
            db=db, user_qiao_id=user_qiao_id, count=recommend_count, category=category
        )

        # Transform to response format
        items = []
        for template in templates:
            # Convert DB string category to API integer (Profile category)
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

        # Calculate next available refresh time
        window = int(
            await system_configs.get_config_value(
                db, config_key="square_rate_limit_window", default_value=10
            )
        )
        refresh_available_at = datetime.utcnow() + timedelta(seconds=window)

        logger.info(
            "square_contacts_retrieved",
            user_qiao_id=user_qiao_id,
            count=len(items),
            category=category,
            force_refresh=force_refresh,
        )

        return SquareContactListResponse(items=items, refresh_available_at=refresh_available_at)

    except ValueError:
        # Re-raise ValueError (rate limit error)
        raise
    except Exception as e:
        logger.error(
            "square_contacts_service_error", user_qiao_id=user_qiao_id, category=category, error=str(e)
        )
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
