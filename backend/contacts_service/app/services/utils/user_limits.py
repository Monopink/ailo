"""
User limits utility functions
Handles user permission and limit checking logic
"""

from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from ...models.user import User
from ...models.contact import Contact
from ...core.config import settings
from ...utils.logging import get_logger

logger = get_logger(__name__)


async def get_user_contact_limits(session: AsyncSession, user_entity_id: str) -> Dict[str, Any]:
    """
    Get user's contact limits and current count

    Args:
        session: Database session
        user_entity_id: User's entity ID

    Returns:
        Dictionary with contact limits and current count
    """
    try:
        # Get user settings
        user_result = await session.execute(select(User).where(User.entity_id == user_entity_id))
        user = user_result.scalar_one_or_none()

        if not user:
            raise ValueError(f"User not found: {user_entity_id}")

        # Count current contacts
        contact_count_result = await session.execute(
            select(func.count(Contact.id)).where(
                Contact.user_entity_id == user_entity_id,
                Contact.contact_type == 2,  # bot contacts only
                Contact.status == 1,  # normal status only
            )
        )
        current_count = contact_count_result.scalar() or 0

        # Calculate limits - use database values, fallback to config defaults with warning
        if user.contact_limit is None:
            logger.warning(
                "user_contact_limit_null_using_default",
                user_entity_id=user_entity_id,
                user_id=user.id,
                default_value=settings.DEFAULT_CONTACT_LIMIT,
                message="User contact_limit is NULL, using configuration default",
            )
            contact_limit = settings.DEFAULT_CONTACT_LIMIT
        else:
            contact_limit = user.contact_limit

        if user.search_display_limit is None:
            logger.warning(
                "user_search_display_limit_null_using_default",
                user_entity_id=user_entity_id,
                user_id=user.id,
                default_value=settings.DEFAULT_SEARCH_DISPLAY_LIMIT,
                message="User search_display_limit is NULL, using configuration default",
            )
            search_display_limit = settings.DEFAULT_SEARCH_DISPLAY_LIMIT
        else:
            search_display_limit = user.search_display_limit
        can_add_more = current_count < contact_limit

        return {
            "current_count": current_count,
            "contact_limit": contact_limit,
            "search_display_limit": search_display_limit,
            "can_add_more": can_add_more,
        }

    except Exception as e:
        logger.error("get_user_contact_limits_error", error=str(e), user_entity_id=user_entity_id)
        raise


def check_contact_limit_reached(limits_info: Dict[str, Any]) -> bool:
    """
    Check if user has reached contact limit

    Args:
        limits_info: Result from get_user_contact_limits

    Returns:
        True if limit reached, False otherwise
    """
    return not limits_info.get("can_add_more", False)


def get_search_display_limit(limits_info: Dict[str, Any]) -> int:
    """
    Get search display limit from limits info

    Args:
        limits_info: Result from get_user_contact_limits

    Returns:
        Search display limit
    """
    return limits_info.get("search_display_limit", 2)
