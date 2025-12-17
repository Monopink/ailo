"""
Avatar URL generation utilities.

Provides helper functions for generating avatar URLs from profile.avatar_file_id,
with support for both single and batch queries to avoid N+1 query problems.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.message import media_file as media_file_crud
from app.enums import FileStatus
from app.models.message.media import MediaFile
from app.models.profile import Profile
from app.services.media.url import build_public_url

DEFAULT_AVATAR_FILE_ID = "file_preset_default"


async def _get_default_avatar_url(db: AsyncSession) -> str:
    """Resolve the system default avatar URL or raise if misconfigured."""
    default_media = await media_file_crud.get_by_file_id(db, file_id=DEFAULT_AVATAR_FILE_ID)
    if not default_media or default_media.status != int(FileStatus.ACTIVE):
        raise ValueError(f"System default avatar not found or inactive: {DEFAULT_AVATAR_FILE_ID}")
    return build_public_url(default_media)


async def get_avatar_url(db: AsyncSession, profile: Profile | None) -> str:
    """
    Generate avatar URL for a profile with fallback to the system default avatar.

    Args:
        db: Database session
        profile: Profile object (may be None)

    Returns:
        Avatar CDN URL (never None). Falls back to DEFAULT_AVATAR_FILE_ID when
        user profile has no avatar or the custom avatar is inactive.

    Example:
        >>> profile = await profile_crud.get_by_owner(
        ...     db, owner_id=user.id, owner_type=ProfileOwnerType.USER
        ... )
        >>> avatar_url = await get_avatar_url(db, profile)
    """
    if profile and profile.avatar_file_id:
        media_file = await media_file_crud.get(db, id=profile.avatar_file_id)
        if media_file and media_file.status == int(FileStatus.ACTIVE):
            return build_public_url(media_file)

    return await _get_default_avatar_url(db)


async def get_avatar_urls_batch(db: AsyncSession, profiles: list[Profile]) -> dict[int, str]:
    """
    Batch generate avatar URLs for multiple profiles.

    This function performs a single database query to fetch all required media_files,
    avoiding N+1 query problems when loading avatar URLs for lists (contacts, discovery, etc.).

    Args:
        db: Database session
        profiles: List of Profile objects

    Returns:
        Dictionary mapping profile.id -> avatar_url
        Profiles without avatars or with inactive files will not appear in the result

    Example:
        >>> # Get contacts list
        >>> contacts = await contact_crud.get_user_contacts(db, user_id=current_user.id)
        >>> profiles = [contact.profile for contact in contacts if contact.profile]
        >>>
        >>> # Batch fetch avatar URLs (single query)
        >>> avatar_urls = await get_avatar_urls_batch(db, profiles)
        >>>
        >>> # Use in response
        >>> for contact in contacts:
        >>>     avatar_url = avatar_urls.get(contact.profile.id) if contact.profile else None
    """
    if not profiles:
        return {}

    # Extract file IDs from profiles
    file_ids = [p.avatar_file_id for p in profiles if p.avatar_file_id]

    file_id_to_url: dict[int, str] = {}
    if file_ids:
        # Batch query media_files (single SQL query)
        result = await db.execute(
            select(MediaFile).where(
                MediaFile.id.in_(file_ids), MediaFile.status == int(FileStatus.ACTIVE)
            )
        )
        media_files = result.scalars().all()

        # Build mapping: file_id -> CDN URL
        file_id_to_url = {mf.id: build_public_url(mf) for mf in media_files}

    default_url = await _get_default_avatar_url(db)

    # Build result: profile_id -> avatar_url
    result_map: dict[int, str] = {}
    for profile in profiles:
        if profile.avatar_file_id and profile.avatar_file_id in file_id_to_url:
            result_map[profile.id] = file_id_to_url[profile.avatar_file_id]
        else:
            result_map[profile.id] = default_url

    return result_map
