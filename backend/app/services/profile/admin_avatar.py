"""
Admin profile avatar update service.
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.profile_logs import write_user_profile_change_log
from app.enums import FileType, ProfileModifierType, ProfileOwnerType, UploaderType
from app.models.message import MediaFile
from app.models.profile import Profile
from app.services.media.avatar_image import AvatarCrop, normalize_avatar_image
from app.services.media.uploader import (
    UploadActor,
    UploadOwnership,
    upload_via_proxy_for_actor,
)
from app.services.storage.base import StorageError
from app.services.storage.factory import get_storage_backend
from app.utils.logging import get_logger

logger = get_logger(__name__)


async def apply_admin_avatar_to_profile(
    db: AsyncSession,
    *,
    profile: Profile,
    media_file: MediaFile,
) -> None:
    """Bind avatar media file to profile and write audit log."""
    old_media_id = profile.avatar_media_id
    new_media_id = media_file.id

    profile.avatar_key = media_file.object_key
    profile.avatar_media_id = new_media_id
    db.add(profile)

    await write_user_profile_change_log(
        db,
        owner_id=profile.owner_id,
        owner_qiao_id=profile.owner_qiao_id,
        owner_type=profile.owner_type,
        modified_by_type=ProfileModifierType.ADMIN,
        field_name="avatar_media_id",
        old_value=old_media_id,
        new_value=new_media_id,
        change_reason="admin_avatar_upload",
    )
    await db.flush()


async def clear_admin_avatar_for_profile(db: AsyncSession, *, profile: Profile) -> Profile:
    """Clear avatar fields and write audit log when value changes."""
    old_media_id = profile.avatar_media_id

    profile.avatar_key = None
    profile.avatar_media_id = None
    db.add(profile)

    await write_user_profile_change_log(
        db,
        owner_id=profile.owner_id,
        owner_qiao_id=profile.owner_qiao_id,
        owner_type=profile.owner_type,
        modified_by_type=ProfileModifierType.ADMIN,
        field_name="avatar_media_id",
        old_value=old_media_id,
        new_value=None,
        change_reason="admin_avatar_clear",
    )

    await db.commit()
    await db.refresh(profile)
    return profile


async def upload_admin_avatar_for_profile(
    db: AsyncSession,
    *,
    profile: Profile,
    actor: UploadActor,
    file_bytes: bytes,
    mime_type: str,
    file_size: int,
    original_name: str | None,
    crop: AvatarCrop | None,
) -> tuple[Profile, bool]:
    """Upload avatar media and atomically apply to profile with audit logging."""
    ownership = _resolve_profile_media_ownership(profile)
    upload_result = await upload_via_proxy_for_actor(
        db,
        actor=actor,
        file_bytes=file_bytes,
        file_type=FileType.AVATAR,
        mime_type=mime_type,
        file_size=file_size,
        original_name=original_name,
        file_hash=None,
        transform=lambda payload, payload_mime: normalize_avatar_image(
            file_bytes=payload, mime_type=payload_mime, crop=crop
        ),
        ownership=ownership,
        enforce_quota=False,
        commit=False,
    )

    await apply_admin_avatar_to_profile(db, profile=profile, media_file=upload_result.media_file)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        _compensate_uploaded_object(upload_result.uploaded_object_key)
        raise

    await db.refresh(profile)
    return profile, upload_result.deduplicated


def _resolve_profile_media_ownership(profile: Profile) -> UploadOwnership:
    """Map profile owner identity to media ownership for deduplication and ownership checks."""
    if profile.owner_type == int(ProfileOwnerType.USER):
        uploader_type = UploaderType.USER
    elif profile.owner_type in (
        int(ProfileOwnerType.AI_PERSONA),
        int(ProfileOwnerType.AI_INSTANCE),
    ):
        uploader_type = UploaderType.SYSTEM
    else:
        raise HTTPException(status_code=400, detail="不支持的资料拥有者类型")

    return UploadOwnership(
        uploader_type=uploader_type,
        uploader_id=profile.owner_id,
        uploader_qiao_id=profile.owner_qiao_id,
    )


def _compensate_uploaded_object(object_key: str | None) -> None:
    """Delete uploaded object when DB transaction fails after upload."""
    if not object_key:
        return
    storage = get_storage_backend()
    try:
        storage.delete(object_key)
    except StorageError as exc:
        logger.error(
            "admin_avatar_upload_compensation_failed",
            object_key=object_key,
            error=str(exc),
        )
