"""Admin profile avatar management APIs."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse

from app.api.deps import get_db, verify_admin_session
from app.enums import FileType, ProfileOwnerType, UploaderType
from app.models.ai.instance import AIInstance
from app.models.ai.template import AIPersona
from app.models.profile import Profile
from app.models.user import User
from app.services.media.avatar_image import AvatarCrop
from app.services.media.uploader import UploadActor
from app.services.profile.admin_avatar import (
    clear_admin_avatar_for_profile,
    upload_admin_avatar_for_profile,
)
from app.services.profile.avatar import get_avatar_url
from app.utils.logging import get_logger

logger = get_logger(__name__)

profile_router = APIRouter()


class AdminProfileAvatarUploadResponse(BaseModel):
    """Response payload for admin profile avatar upload."""

    profile_id: int = Field(..., description="Target profile ID")
    avatar_media_id: int | None = Field(None, description="Bound media ID")
    avatar_url: str = Field(..., description="Resolved profile avatar URL")
    duplicate: bool = Field(..., description="Whether upload hit deduplication")


class AdminProfileAvatarClearResponse(BaseModel):
    """Response payload for admin profile avatar clear."""

    profile_id: int = Field(..., description="Target profile ID")
    avatar_media_id: int | None = Field(None, description="Cleared media ID (always null)")
    avatar_url: str = Field(..., description="Resolved profile avatar URL")


def _require_admin_identity(admin_user: dict[str, Any]) -> tuple[int, str]:
    raw_admin_id = admin_user.get("id")
    raw_username = admin_user.get("username")
    if not isinstance(raw_admin_id, int) or raw_admin_id <= 0:
        raise HTTPException(status_code=401, detail="Authentication required")
    if not isinstance(raw_username, str) or not raw_username:
        raise HTTPException(status_code=401, detail="Authentication required")
    return raw_admin_id, raw_username


async def _get_profile_or_404(db: AsyncSession, profile_id: int) -> Profile:
    profile = await db.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


async def _resolve_profile_by_owner_or_404(
    db: AsyncSession,
    *,
    owner_kind: str,
    owner_id: int,
) -> Profile:
    if owner_kind == "user":
        owner_user = await db.get(User, owner_id)
        if owner_user is None:
            raise HTTPException(status_code=404, detail="User not found")
        stmt = select(Profile).where(
            Profile.owner_id == owner_user.id,
            Profile.owner_type == int(ProfileOwnerType.USER),
        )
    elif owner_kind == "ai_persona":
        owner_persona = await db.get(AIPersona, owner_id)
        if owner_persona is None:
            raise HTTPException(status_code=404, detail="AI persona not found")
        stmt = select(Profile).where(
            Profile.owner_id == owner_persona.id,
            Profile.owner_type == int(ProfileOwnerType.AI_PERSONA),
        )
    elif owner_kind == "ai_instance":
        owner_instance = await db.get(AIInstance, owner_id)
        if owner_instance is None:
            raise HTTPException(status_code=404, detail="AI instance not found")
        stmt = select(Profile).where(
            Profile.owner_qiao_id == owner_instance.qiao_id,
            Profile.owner_type.in_(
                [int(ProfileOwnerType.AI_INSTANCE), int(ProfileOwnerType.AI_PERSONA)]
            ),
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid owner kind")

    profile = (await db.execute(stmt)).scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@profile_router.post(
    "/profile/{profile_id}/avatar/upload",
    response_model=AdminProfileAvatarUploadResponse,
)
async def upload_profile_avatar(
    profile_id: int,
    file: UploadFile = File(...),
    file_type: int = Form(...),
    mime_type: str = Form(...),
    file_size: int = Form(...),
    original_name: str | None = Form(None),
    crop_x: int | None = Form(None),
    crop_y: int | None = Form(None),
    crop_size: int | None = Form(None),
    db: AsyncSession = Depends(get_db),
    admin_user: dict[str, Any] = Depends(verify_admin_session),
) -> AdminProfileAvatarUploadResponse:
    """Upload avatar image for a profile via admin session."""
    if file_type != int(FileType.AVATAR):
        raise HTTPException(status_code=400, detail="当前仅支持头像上传")

    admin_id, admin_username = _require_admin_identity(admin_user)
    profile = await _get_profile_or_404(db, profile_id)

    file_bytes = await file.read()
    await file.close()
    resolved_original_name = original_name or file.filename

    crop: AvatarCrop | None = None
    if crop_x is not None and crop_y is not None and crop_size is not None:
        crop = AvatarCrop(x=crop_x, y=crop_y, size=crop_size)

    actor = UploadActor(
        uploader_type=UploaderType.ADMIN,
        uploader_id=admin_id,
        uploader_qiao_id=admin_username,
        rate_limit_subject=f"admin:{admin_id}",
        confirmed_by_id=admin_id,
    )

    updated_profile, deduplicated = await upload_admin_avatar_for_profile(
        db,
        profile=profile,
        actor=actor,
        file_bytes=file_bytes,
        mime_type=mime_type,
        file_size=file_size,
        original_name=resolved_original_name,
        crop=crop,
    )
    avatar_url = await get_avatar_url(updated_profile)
    logger.info(
        "admin_profile_avatar_uploaded",
        profile_id=profile_id,
        avatar_media_id=updated_profile.avatar_media_id,
        admin_user_id=admin_id,
        deduplicated=deduplicated,
    )
    return AdminProfileAvatarUploadResponse(
        profile_id=updated_profile.id,
        avatar_media_id=updated_profile.avatar_media_id,
        avatar_url=avatar_url,
        duplicate=deduplicated,
    )


@profile_router.post(
    "/profile/{profile_id}/avatar/clear",
    response_model=AdminProfileAvatarClearResponse,
)
async def clear_profile_avatar(
    profile_id: int,
    db: AsyncSession = Depends(get_db),
    admin_user: dict[str, Any] = Depends(verify_admin_session),
) -> AdminProfileAvatarClearResponse:
    """Clear profile avatar and fallback to default avatar URL."""
    admin_id, _ = _require_admin_identity(admin_user)
    profile = await _get_profile_or_404(db, profile_id)

    updated_profile = await clear_admin_avatar_for_profile(db, profile=profile)
    avatar_url = await get_avatar_url(updated_profile)
    logger.info(
        "admin_profile_avatar_cleared",
        profile_id=profile_id,
        admin_user_id=admin_id,
    )
    return AdminProfileAvatarClearResponse(
        profile_id=updated_profile.id,
        avatar_media_id=updated_profile.avatar_media_id,
        avatar_url=avatar_url,
    )


@profile_router.get("/profile/owner-link/{owner_kind}/{owner_id}")
async def profile_owner_link(
    owner_kind: str,
    owner_id: int,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Resolve owner to profile and redirect to admin profile detail page."""
    profile = await _resolve_profile_by_owner_or_404(
        db,
        owner_kind=owner_kind,
        owner_id=owner_id,
    )
    return RedirectResponse(url=f"/qiao-dash/profile/detail/{profile.id}", status_code=303)
