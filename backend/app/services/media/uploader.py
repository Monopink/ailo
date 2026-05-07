"""
Media upload orchestration (proxy-only flow).
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.crud.message import media_file as media_file_crud
from app.enums import FileStatus, FileType, UploaderType
from app.models.message import MediaFile
from app.models.user import User
from app.services.media.quota import enforce_daily_quota
from app.services.media.rules import get_file_type_rule
from app.services.security.rate_limiter import check_rate_limit
from app.services.storage.base import StorageError
from app.services.storage.factory import get_storage_backend
from app.services.storage.utils import generate_file_id, generate_object_key
from app.services.system_config import get_config_int, get_config_str_list
from app.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class UploadActor:
    """Runtime uploader context for media proxy upload."""

    uploader_type: UploaderType
    uploader_id: int
    uploader_qiao_id: str
    rate_limit_subject: str
    confirmed_by_id: int | None = None


@dataclass(frozen=True)
class UploadOwnership:
    """Media record ownership scope."""

    uploader_type: UploaderType
    uploader_id: int
    uploader_qiao_id: str


@dataclass(frozen=True)
class UploadResult:
    """Upload operation result."""

    media_file: MediaFile
    deduplicated: bool
    uploaded_object_key: str | None


UploadTransform = Callable[[bytes, str], tuple[bytes, str]]


async def upload_via_proxy(
    db: AsyncSession,
    *,
    user: User,
    file_bytes: bytes,
    file_type: FileType,
    mime_type: str,
    file_size: int,
    original_name: str | None,
    file_hash: str | None,
) -> tuple[MediaFile, bool]:
    """Handle backend-proxied uploads for user JWT flow."""

    actor = UploadActor(
        uploader_type=UploaderType.USER,
        uploader_id=user.id,
        uploader_qiao_id=user.qiao_id,
        rate_limit_subject=user.qiao_id,
        confirmed_by_id=user.id,
    )
    result = await upload_via_proxy_for_actor(
        db,
        actor=actor,
        file_bytes=file_bytes,
        file_type=file_type,
        mime_type=mime_type,
        file_size=file_size,
        original_name=original_name,
        file_hash=file_hash,
        ownership=UploadOwnership(
            uploader_type=actor.uploader_type,
            uploader_id=actor.uploader_id,
            uploader_qiao_id=actor.uploader_qiao_id,
        ),
        enforce_quota=True,
        commit=True,
    )
    return result.media_file, result.deduplicated


async def upload_via_proxy_for_actor(
    db: AsyncSession,
    *,
    actor: UploadActor,
    file_bytes: bytes,
    file_type: FileType,
    mime_type: str,
    file_size: int,
    original_name: str | None,
    file_hash: str | None,
    transform: UploadTransform | None = None,
    ownership: UploadOwnership | None = None,
    enforce_quota: bool = True,
    commit: bool = True,
) -> UploadResult:
    """Handle backend-proxied uploads with reusable actor context."""

    settings = get_settings()
    rule = get_file_type_rule(file_type)
    if not rule:
        raise HTTPException(status_code=400, detail="当前仅支持头像上传")

    actual_size = len(file_bytes)

    # Allow file_size=0 as signal from DevTools where FileSystemManager APIs
    # don't support http://tmp/... protocol. Use actual size for validation.
    if file_size == 0:
        file_size = actual_size
        logger.info(
            "file_size_auto_detected",
            uploader_id=actor.uploader_id,
            actual_size=actual_size,
            file_type=file_type.name,
        )
    elif actual_size != file_size:
        raise HTTPException(status_code=400, detail="文件大小不匹配，请重新选择图片")

    resolved_ownership = ownership or UploadOwnership(
        uploader_type=actor.uploader_type,
        uploader_id=actor.uploader_id,
        uploader_qiao_id=actor.uploader_qiao_id,
    )

    if enforce_quota:
        await enforce_daily_quota(
            db,
            uploader_type=resolved_ownership.uploader_type,
            uploader_id=resolved_ownership.uploader_id,
            file_type=file_type,
            file_size=actual_size,
        )

    allowed, _, retry_after = await check_rate_limit(actor.rate_limit_subject, "media_upload", db)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="上传过于频繁，请稍后再试",
            headers={"Retry-After": str(retry_after or 60)},
        )

    max_size_mb = await get_config_int(db, rule.max_size_key)
    max_size_bytes = max_size_mb * 1024 * 1024
    if actual_size > max_size_bytes:
        raise HTTPException(status_code=413, detail=f"文件大小超过限制（{max_size_mb}MB）")

    allowed_mimes = await _get_allowed_mimes(db, rule.allowed_mimes_key)
    if mime_type.lower() not in allowed_mimes:
        raise HTTPException(status_code=415, detail="不支持的文件格式")

    transformed_bytes = file_bytes
    transformed_mime = mime_type
    if transform is not None:
        transformed_bytes, transformed_mime = transform(file_bytes, mime_type)
        if not transformed_bytes:
            raise HTTPException(status_code=400, detail="图片处理失败")
        if transformed_mime.lower() not in allowed_mimes:
            raise HTTPException(status_code=415, detail="不支持的文件格式")

    provided_hash = file_hash.lower() if file_hash and transform is None else None
    effective_hash = provided_hash or hashlib.sha256(transformed_bytes).hexdigest()

    duplicate = None
    if effective_hash:
        duplicate = await media_file_crud.find_active_duplicate(
            db,
            uploader_type=resolved_ownership.uploader_type,
            uploader_id=resolved_ownership.uploader_id,
            file_type=file_type,
            file_hash=effective_hash,
        )

    if duplicate:
        logger.info(
            "media_proxy_upload_deduplicated",
            uploader_id=actor.uploader_id,
            uploader_type=actor.uploader_type.name,
            file_type=file_type.name,
            file_id=duplicate.file_id,
        )
        return UploadResult(
            media_file=duplicate,
            deduplicated=True,
            uploaded_object_key=None,
        )

    storage = get_storage_backend()
    object_key = generate_object_key(int(file_type), transformed_mime)
    file_id = generate_file_id()
    original_name_value = original_name or object_key.split("/")[-1]

    try:
        # Call storage.upload() directly - boto3 is thread-safe in uvicorn worker
        storage.upload(
            object_key,
            transformed_bytes,
            transformed_mime,
            is_public=rule.is_public,
        )
    except StorageError as exc:
        logger.error("media_proxy_upload_failed", error=str(exc))
        raise HTTPException(status_code=503, detail="系统错误") from exc

    record = MediaFile(
        file_id=file_id,
        file_type=int(file_type),
        storage_provider=storage.provider_name,
        bucket_name=settings.TENCENT_COS_MEDIA_BUCKET,
        object_key=object_key,
        storage_region=settings.TENCENT_COS_MEDIA_REGION,
        original_name=original_name_value,
        file_size=len(transformed_bytes),
        mime_type=transformed_mime,
        file_hash=effective_hash,
        is_public=rule.is_public,
        upload_by_type=int(resolved_ownership.uploader_type),
        upload_by_id=resolved_ownership.uploader_id,
        upload_by_qiao_id=resolved_ownership.uploader_qiao_id,
        status=int(FileStatus.ACTIVE),
        confirmed_at=datetime.now(UTC),
        confirmed_by_id=actor.confirmed_by_id
        if actor.confirmed_by_id is not None
        else actor.uploader_id,
    )

    db.add(record)
    if commit:
        await db.commit()
        await db.refresh(record)
    else:
        await db.flush()

    logger.info(
        "media_proxy_upload_succeeded",
        file_id=record.file_id,
        uploader_id=actor.uploader_id,
        uploader_type=actor.uploader_type.name,
    )
    return UploadResult(
        media_file=record,
        deduplicated=False,
        uploaded_object_key=object_key,
    )


async def _get_allowed_mimes(db: AsyncSession, config_key: str) -> list[str]:
    allowed_items = await get_config_str_list(db, config_key)
    return [item.strip().lower() for item in allowed_items if item.strip()]
