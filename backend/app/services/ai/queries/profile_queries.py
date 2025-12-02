"""
User profile-related query functions.

This module provides user profile-related read/query functions with clear
separation of concerns and pure function design.
"""

from typing import Any

from models.profile import Profile
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from utils.logging import get_logger

logger = get_logger(__name__)


async def get_user_profile(db: AsyncSession, user_qiao_id: str) -> dict[str, Any] | None:
    """
    Get user profile information.

    Args:
        db: Database session
        user_qiao_id: User's qiao_id

    Returns:
        Dictionary containing user profile, or None if not found
    """
    try:
        result = await db.execute(
            select(Profile).where(
                and_(Profile.owner_qiao_id == user_qiao_id, Profile.owner_type == 1)  # User type
            )
        )

        profile = result.scalar_one_or_none()
        if not profile:
            logger.warning("user_profile_not_found", user_qiao_id=user_qiao_id)
            return None

        return {
            "profile": profile,
            "nickname": profile.nickname,
            "bio": profile.bio,
            "avatar_url": profile.avatar_url,
            "gender": getattr(profile, "gender", None),
            "age": getattr(profile, "age", None),
            "location": getattr(profile, "location", None),
        }

    except Exception as e:
        logger.error("user_profile_query_failed", error=str(e), user_qiao_id=user_qiao_id)
        return None


async def get_instance_profile(db: AsyncSession, instance_qiao_id: str) -> dict[str, Any] | None:
    """
    Get instance profile information.

    Args:
        db: Database session
        instance_qiao_id: Instance's qiao_id

    Returns:
        Dictionary containing instance profile, or None if not found
    """
    try:
        result = await db.execute(
            select(Profile).where(
                and_(Profile.owner_qiao_id == instance_qiao_id, Profile.owner_type == 2)  # AI type
            )
        )

        profile = result.scalar_one_or_none()
        if not profile:
            logger.warning("instance_profile_not_found", instance_qiao_id=instance_qiao_id)
            return None

        return {
            "profile": profile,
            "nickname": profile.nickname,
            "bio": profile.bio,
            "avatar_url": profile.avatar_url,
            "gender": getattr(profile, "gender", None),
            "age": getattr(profile, "age", None),
            "location": getattr(profile, "location", None),
        }

    except Exception as e:
        logger.error(
            "instance_profile_query_failed", error=str(e), instance_qiao_id=instance_qiao_id
        )
        return None


async def get_profile_by_owner(
    db: AsyncSession, owner_qiao_id: str, owner_type: int
) -> Profile | None:
    """
    Get profile by owner qiao_id and type.

    Args:
        db: Database session
        owner_qiao_id: Owner's qiao_id
        owner_type: Owner type (1=user, 2=AI)

    Returns:
        Profile object or None if not found
    """
    try:
        result = await db.execute(
            select(Profile).where(
                and_(Profile.owner_qiao_id == owner_qiao_id, Profile.owner_type == owner_type)
            )
        )

        profile = result.scalar_one_or_none()

        if not profile:
            logger.debug("profile_not_found", owner_qiao_id=owner_qiao_id, owner_type=owner_type)

        return profile

    except Exception as e:
        logger.error(
            "profile_by_owner_query_failed",
            error=str(e),
            owner_qiao_id=owner_qiao_id,
            owner_type=owner_type,
        )
        return None
