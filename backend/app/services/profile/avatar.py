"""
Avatar URL generation utilities.

Provides helper functions for generating avatar URLs from profile.avatar_key.
Zero-JOIN implementation for maximum performance.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import MissingConfigurationError
from app.models.profile import Profile
from app.services.media.config import (
    get_media_base_url,
    refresh_media_base_url,
)
from app.utils.logging import get_logger

DEFAULT_AVATAR_OBJECT_KEY = "avatars/default.webp"
logger = get_logger(__name__)


async def get_avatar_url(profile: Profile | None) -> str:
    """
    Generate avatar URL for a profile with fallback to the system default avatar.

    Args:
        profile: Profile object (may be None)

    Returns:
        Avatar CDN URL (never None). Falls back to the predefined default avatar
        when user profile has no avatar_key set.

    Example:
        >>> profile = await profile_crud.get_by_owner(
        ...     db, owner_id=user.id, owner_type=ProfileOwnerType.USER
        ... )
        >>> avatar_url = await get_avatar_url(profile)
    """
    base = _resolve_media_base_url()
    if not base:
        return ""

    object_key = profile.avatar_key if profile and profile.avatar_key else DEFAULT_AVATAR_OBJECT_KEY
    return f"{base}/{object_key}"


async def get_avatar_urls_batch(profiles: list[Profile]) -> dict[int, str]:
    """
    Batch generate avatar URLs for multiple profiles.

    Zero-JOIN implementation using avatar_key for maximum performance.

    Args:
        profiles: List of Profile objects

    Returns:
        Dictionary mapping profile.id -> avatar_url
        All profiles will have an entry (default avatar if avatar_key is NULL)

    Example:
        >>> # Get contacts list
        >>> contacts = await contact_crud.get_user_contacts(db, user_id=current_user.id)
        >>> profiles = [contact.profile for contact in contacts if contact.profile]
        >>>
        >>> # Batch fetch avatar URLs (zero database queries!)
        >>> avatar_urls = await get_avatar_urls_batch(profiles)
        >>>
        >>> # Use in response
        >>> for contact in contacts:
        >>>     avatar_url = avatar_urls.get(contact.profile.id) if contact.profile else None
    """
    if not profiles:
        return {}

    base = _resolve_media_base_url()
    if not base:
        return {}

    # Build result: profile_id -> avatar_url (zero database queries)
    result_map: dict[int, str] = {}
    for profile in profiles:
        object_key = profile.avatar_key if profile.avatar_key else DEFAULT_AVATAR_OBJECT_KEY
        result_map[profile.id] = f"{base}/{object_key}"

    return result_map


def _resolve_media_base_url() -> str:
    """Return normalized media base URL or empty string if unavailable."""
    try:
        return get_media_base_url()
    except MissingConfigurationError:
        logger.error("media_public_base_url_missing")
        return ""


async def get_default_avatar_url(db: AsyncSession) -> str:
    """
    Return the canonical default avatar URL with system config priority.
    """
    base = await refresh_media_base_url(db)
    if not base:
        logger.error("default_avatar_base_missing")
        raise MissingConfigurationError(config_key="media_public_base_url")
    return f"{base}/{DEFAULT_AVATAR_OBJECT_KEY}"
