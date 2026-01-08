"""Media upload and asset endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.crud.message import media_file as media_file_crud
from app.enums import FileStatus, FileType
from app.models.user import User
from app.schemas.media import MediaAccessResponse, MediaUploadResponse
from app.services.media.uploader import upload_via_proxy
from app.services.media.url import build_private_url, build_public_url

router = APIRouter(prefix="/media", tags=["Media"])


@router.post("/upload", response_model=MediaUploadResponse)
async def upload_media_via_proxy(
    file: UploadFile = File(...),
    file_type: int = Form(...),
    mime_type: str = Form(...),
    file_size: int = Form(...),
    original_name: str | None = Form(None),
    file_hash: str | None = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MediaUploadResponse:
    """Upload media via backend proxy (mini program/admin)."""
    try:
        file_type_enum = FileType(file_type)
    except ValueError as exc:  # pragma: no cover - FastAPI validation should guard
        raise HTTPException(status_code=400, detail="当前仅支持头像上传") from exc

    file_bytes = await file.read()
    await file.close()
    resolved_original_name = original_name or file.filename

    confirmed_file, deduplicated = await upload_via_proxy(
        db,
        user=current_user,
        file_bytes=file_bytes,
        file_type=file_type_enum,
        mime_type=mime_type,
        file_size=file_size,
        original_name=resolved_original_name,
        file_hash=file_hash,
    )

    url = build_public_url(confirmed_file)
    return MediaUploadResponse(file_id=confirmed_file.file_id, url=url, duplicate=deduplicated)


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
