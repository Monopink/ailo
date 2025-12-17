"""
Media upload and asset endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.crud.message import media_file as media_file_crud
from app.enums import FileStatus
from app.models.user import User
from app.schemas.media import (
    MediaAccessResponse,
    UploadConfirmRequest,
    UploadConfirmResponse,
    UploadTokenRequest,
    UploadTokenResponse,
)
from app.services.media.uploader import confirm_upload, request_upload_token
from app.services.media.url import build_private_url, build_public_url

router = APIRouter(prefix="/media", tags=["Media"])


@router.post("/upload-token", response_model=UploadTokenResponse)
async def generate_upload_token(
    payload: UploadTokenRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UploadTokenResponse:
    """Issue presigned upload URL or short-circuit via deduplication."""
    result = await request_upload_token(
        db,
        user=current_user,
        file_type=payload.file_type,
        mime_type=payload.mime_type,
        file_size=payload.file_size,
        original_name=payload.original_name,
        file_hash=payload.file_hash,
    )
    return UploadTokenResponse(
        file_id=result.file_id,
        upload_url=result.upload_url,
        object_key=result.object_key,
        expires_in=result.expires_in,
        url=result.url,
        duplicate=result.duplicate,
    )


@router.post("/upload-confirm", response_model=UploadConfirmResponse)
async def finalize_upload(
    payload: UploadConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UploadConfirmResponse:
    """Confirm object upload, verify metadata, and activate record."""
    media = await media_file_crud.get_by_file_id(db, file_id=payload.file_id)
    if not media:
        raise HTTPException(status_code=404, detail="文件不存在")

    confirmed_file, deduplicated = await confirm_upload(
        db, user=current_user, media=media, etag=payload.etag
    )

    url = build_public_url(confirmed_file)
    return UploadConfirmResponse(file_id=confirmed_file.file_id, url=url, duplicate=deduplicated)


@router.get("/{file_id}", response_model=MediaAccessResponse)
async def get_media_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MediaAccessResponse:
    """Resolve file metadata and return URL (public or presigned)."""
    media = await media_file_crud.get_by_file_id(db, file_id=file_id)
    if not media or media.status != int(FileStatus.ACTIVE):
        raise HTTPException(status_code=404, detail="文件不存在")

    if media.upload_by_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作")

    if media.is_public:
        url = build_public_url(media)
    else:
        url = build_private_url(media)

    return MediaAccessResponse(
        file_id=media.file_id,
        url=url,
        mime_type=media.mime_type,
        file_size=media.file_size,
        created_at=media.created_at,
    )
