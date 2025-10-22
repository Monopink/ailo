"""
Discovery service business logic.

This module provides business logic for discovery page operations.
"""

from datetime import datetime, timedelta
from typing import Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from crud.system import system_configs
from schemas.discovery import SquareContactResponse, SquareContactListResponse
from services.discovery import data as discovery_data
from utils.logging import get_logger

logger = get_logger(__name__)

# In-memory cache for refresh rate limiting (MVP solution)
# Key: user_qiao_id, Value: last_refresh_time
_refresh_cache: Dict[str, datetime] = {}


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
        refresh_interval = await system_configs.get_config_value(
            db, config_key="square_refresh_interval", default_value=60
        )

        # Convert to int/float
        recommend_count = int(recommend_count)
        refresh_interval = float(refresh_interval)

        logger.debug(
            "square_config_loaded", recommend_count=recommend_count, refresh_interval=refresh_interval
        )

        # Check refresh rate limit
        if not force_refresh:
            last_refresh = _refresh_cache.get(user_qiao_id)
            if last_refresh:
                elapsed = (datetime.utcnow() - last_refresh).total_seconds()
                if elapsed < refresh_interval:
                    remaining = refresh_interval - elapsed
                    logger.warning(
                        "square_refresh_rate_limit",
                        user_qiao_id=user_qiao_id,
                        elapsed=elapsed,
                        remaining=remaining,
                    )
                    raise ValueError(f"Refresh too frequent, wait {remaining:.0f} seconds")

        # Query random templates
        templates = await discovery_data.get_random_templates(
            db=db, user_qiao_id=user_qiao_id, count=recommend_count, category=category
        )

        # Transform to response format
        items = []
        for template in templates:
            items.append(
                SquareContactResponse(
                    qiao_id=template.qiao_id,
                    category=template.category,
                    nickname=template.nickname,
                    gender=template.gender,
                    avatar_url=template.avatar_url,
                    bio=template.bio,
                    region=template.region,
                )
            )

        # Update refresh cache
        _refresh_cache[user_qiao_id] = datetime.utcnow()

        # Calculate next available refresh time
        refresh_available_at = datetime.utcnow() + timedelta(seconds=refresh_interval)

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
