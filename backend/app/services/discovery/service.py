"""
Discovery service business logic.

This module provides business logic for discovery page operations.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.system import system_configs
from app.enums import SquareCategory
from app.schemas.discovery import (
    PaginationInfo,
    SquareContactListResponse,
    SquareContactResponse,
    StrangerProfileResponse,
)
from app.services.discovery import data as discovery_data
from app.services.profile.avatar import get_avatar_url, get_avatar_urls_batch
from app.services.security.rate_limiter import check_rate_limit
from app.utils.logging import get_logger

logger = get_logger(__name__)


async def get_square_contacts(
    db: AsyncSession,
    user_qiao_id: str,
    category: SquareCategory | None = None,
    page: int = 1,
    page_size: int | None = None,
) -> SquareContactListResponse:
    """
    Get square page contacts with pagination.

    Args:
        db: Database session
        user_qiao_id: Current user's qiao_id
        category: Optional category filter (SquareCategory enum)
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
                await system_configs.get_config_value(
                    db, config_key="square_page_size", default_value=20
                )
            )

        # Check rate limit
        category_key = category.name if category else "all"
        rate_key = f"{user_qiao_id}:{category_key}"
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

        # Query square entries with pagination
        category_value = category.value if category else None
        entries, total = await discovery_data.get_random_persona_entries(
            db=db,
            user_qiao_id=user_qiao_id,
            category=category_value,
            page=page,
            page_size=page_size,
        )

        # Transform to response format
        profiles = [profile for _, _, profile in entries if profile]
        avatar_urls = await get_avatar_urls_batch(db, profiles)

        items = []
        for entry, persona, profile in entries:
            category_api = None
            if entry.square_category is not None:
                try:
                    category_api = SquareCategory(entry.square_category).value
                except ValueError:
                    category_api = None

            avatar_url = avatar_urls.get(profile.id) if profile else None

            items.append(
                SquareContactResponse(
                    qiao_id=persona.qiao_id,
                    type_id=entry.type_id,
                    category=category_api,
                    nickname=getattr(profile, "nickname", None),
                    gender=getattr(profile, "gender", None),
                    avatar_url=avatar_url,
                    bio=getattr(profile, "bio", None),
                    region=getattr(profile, "region", None),
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
        logger.error(
            "square_contacts_service_error",
            user_qiao_id=user_qiao_id,
            category=category,
            error=str(e),
        )
        raise RuntimeError(f"Failed to get square contacts: {e!s}")


async def get_stranger_profile(db: AsyncSession, qiao_id: str) -> StrangerProfileResponse | None:
    """
    Get stranger profile by qiao_id.

    This is a public endpoint that returns basic persona metadata (profiles + square entries)
    without requiring authentication.

    Args:
        db: Database session
        qiao_id: Profile qiao_id to query

    Returns:
        StrangerProfileResponse or None if not found
    """
    try:
        profile, category = await discovery_data.get_persona_profile_by_qiao_id(
            db=db, qiao_id=qiao_id
        )

        if not profile:
            logger.warning("stranger_profile_not_found", qiao_id=qiao_id)
            return None

        # Transform to response format
        category_api = None
        if category is not None:
            try:
                category_api = SquareCategory(category).value
            except ValueError:
                category_api = None

        avatar_url = await get_avatar_url(db, profile)

        response = StrangerProfileResponse(
            qiao_id=profile.owner_qiao_id,
            nickname=profile.nickname,
            gender=profile.gender,
            avatar_url=avatar_url,
            bio=profile.bio,
            region=profile.region,
            category=category_api,
        )

        logger.info("stranger_profile_retrieved", qiao_id=qiao_id)
        return response

    except Exception as e:
        logger.error("stranger_profile_service_error", qiao_id=qiao_id, error=str(e))
        raise RuntimeError(f"Failed to get stranger profile: {e!s}")
