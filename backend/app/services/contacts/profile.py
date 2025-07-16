"""
Profile Service - Social profile management functions
Handles CRUD operations for social profiles
"""

from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from ..models.social_profile import SocialProfile
import structlog

logger = structlog.get_logger(__name__)


async def get_social_profile(session: AsyncSession, entity_id: str) -> Optional[Dict[str, Any]]:
    """
    Get social profile by entity ID

    Args:
        session: Database session
        entity_id: Entity ID

    Returns:
        Social profile dictionary or None if not found
    """
    try:
        result = await session.execute(select(SocialProfile).where(SocialProfile.entity_id == entity_id))
        profile = result.scalar_one_or_none()

        if not profile:
            logger.debug("social_profile_not_found", entity_id=entity_id)
            return None

        return format_profile_for_display(profile)

    except Exception as e:
        logger.error("get_social_profile_error", error=str(e), entity_id=entity_id)
        raise


async def create_social_profile(
    session: AsyncSession, entity_id: str, profile_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Create new social profile

    Args:
        session: Database session
        entity_id: Entity ID for the profile
        profile_data: Profile data dictionary

    Returns:
        Created profile dictionary
    """
    try:
        # Validate profile data
        if not validate_profile_data(profile_data):
            raise ValueError("Invalid profile data")

        # Check if profile already exists
        existing_profile = await get_social_profile(session, entity_id)
        if existing_profile:
            raise ValueError(f"Profile already exists for entity_id: {entity_id}")

        # Create new profile
        new_profile = SocialProfile(
            entity_id=entity_id,
            nickname=profile_data.get("nickname"),
            gender=profile_data.get("gender"),
            avatar_url=profile_data.get("avatar_url"),
            bio=profile_data.get("bio"),
            birth_date=profile_data.get("birth_date"),
            location=profile_data.get("location"),
        )

        session.add(new_profile)
        await session.commit()
        await session.refresh(new_profile)  # Refresh to get the generated ID

        logger.info("social_profile_created", entity_id=entity_id, nickname=profile_data.get("nickname"))

        return format_profile_for_display(new_profile)

    except IntegrityError as e:
        await session.rollback()
        logger.error("social_profile_creation_integrity_error", error=str(e), entity_id=entity_id)
        raise ValueError(f"Profile creation failed due to data integrity: {str(e)}")
    except Exception as e:
        await session.rollback()
        logger.error("create_social_profile_error", error=str(e), entity_id=entity_id)
        raise


async def update_social_profile(
    session: AsyncSession, entity_id: str, updates: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Update existing social profile

    Args:
        session: Database session
        entity_id: Entity ID
        updates: Dictionary of fields to update

    Returns:
        Updated profile dictionary
    """
    try:
        # Get existing profile
        result = await session.execute(select(SocialProfile).where(SocialProfile.entity_id == entity_id))
        profile = result.scalar_one_or_none()

        if not profile:
            raise ValueError(f"Profile not found for entity_id: {entity_id}")

        # Validate update data
        if not validate_profile_data(updates, is_update=True):
            raise ValueError("Invalid update data")

        # Apply updates
        for field, value in updates.items():
            if hasattr(profile, field):
                setattr(profile, field, value)

        await session.commit()

        # Refresh the profile to ensure all attributes are loaded
        await session.refresh(profile)

        logger.info("social_profile_updated", entity_id=entity_id, updated_fields=list(updates.keys()))

        return format_profile_for_display(profile)

    except Exception as e:
        await session.rollback()
        logger.error("update_social_profile_error", error=str(e), entity_id=entity_id)
        raise


async def create_or_update_social_profile(
    session: AsyncSession, entity_id: str, profile_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Create or update social profile (upsert operation)

    Args:
        session: Database session
        entity_id: Entity ID
        profile_data: Profile data dictionary

    Returns:
        Profile dictionary
    """
    try:
        existing_profile = await get_social_profile(session, entity_id)

        if existing_profile:
            return await update_social_profile(session, entity_id, profile_data)
        else:
            return await create_social_profile(session, entity_id, profile_data)

    except Exception as e:
        logger.error("create_or_update_social_profile_error", error=str(e), entity_id=entity_id)
        raise


def validate_profile_data(profile_data: Dict[str, Any], is_update: bool = False) -> bool:
    """
    Validate profile data

    Args:
        profile_data: Profile data to validate
        is_update: Whether this is an update operation

    Returns:
        True if valid, False otherwise
    """
    try:
        # Required fields for creation
        if not is_update:
            if not profile_data.get("nickname"):
                logger.warning("profile_validation_failed", reason="nickname_required")
                return False

        # Validate gender if provided
        gender = profile_data.get("gender")
        if gender and gender not in ["male", "female", "other"]:
            logger.warning("profile_validation_failed", reason="invalid_gender", gender=gender)
            return False

        # Validate nickname length
        nickname = profile_data.get("nickname")
        if nickname and len(nickname) > 50:
            logger.warning("profile_validation_failed", reason="nickname_too_long", length=len(nickname))
            return False

        # Validate bio length
        bio = profile_data.get("bio")
        if bio and len(bio) > 500:
            logger.warning("profile_validation_failed", reason="bio_too_long", length=len(bio))
            return False

        return True

    except Exception as e:
        logger.error("profile_validation_error", error=str(e))
        return False


def format_profile_for_display(profile: SocialProfile) -> Dict[str, Any]:
    """
    Format profile for display/API response

    Args:
        profile: SocialProfile model instance

    Returns:
        Formatted profile dictionary
    """
    # Access all attributes safely to avoid lazy loading issues
    try:
        created_at = profile.created_at.isoformat() if profile.created_at else None
    except Exception:
        created_at = None

    try:
        updated_at = profile.updated_at.isoformat() if profile.updated_at else None
    except Exception:
        updated_at = None

    return {
        "entity_id": profile.entity_id,
        "nickname": profile.nickname,
        "gender": profile.gender,
        "avatar_url": profile.avatar_url,
        "bio": profile.bio,
        "birth_date": profile.birth_date.isoformat() if profile.birth_date else None,
        "location": profile.location,
        "created_at": created_at,
        "updated_at": updated_at,
    }
