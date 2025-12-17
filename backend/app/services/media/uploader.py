"""
Media upload orchestration (token + confirmation).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import cast

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.crud.message import media_file as media_file_crud
from app.enums import FileStatus, FileType, UploaderType
from app.models.message import MediaFile
from app.models.user import User
from app.services.media.quota import enforce_daily_quota
from app.services.media.rules import get_file_type_rule
from app.services.media.url import build_public_url
from app.services.security.rate_limiter import check_rate_limit
from app.services.storage.base import StorageBackend, StorageError, StorageNotFoundError
from app.services.storage.factory import get_storage_backend
from app.services.storage.utils import generate_file_id, generate_object_key
from app.services.system_config import get_config
from app.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class UploadTokenResult:
    file_id: str
    upload_url: str | None = None
    object_key: str | None = None
    expires_in: int | None = None
    url: str | None = None
    duplicate: bool = False


async def request_upload_token(
    db: AsyncSession,
    *,
    user: User,
    file_type: FileType,
    mime_type: str,
    file_size: int,
    original_name: str | None,
    file_hash: str | None,
) -> UploadTokenResult:
    """
    Validate upload intent and either deduplicate or create pending record.

    Returns:
        (duplicate_file, response_payload)
    """

    settings = get_settings()
    rule = get_file_type_rule(file_type)
    if not rule:
        raise HTTPException(status_code=400, detail="当前仅支持头像上传")

    await enforce_daily_quota(db, user_id=user.id, file_type=file_type, file_size=file_size)

    # Rate limit
    allowed, _, retry_after = await check_rate_limit(user.qiao_id, "media_upload", db)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="上传过于频繁，请稍后再试",
            headers={"Retry-After": str(retry_after or 60)},
        )

    max_size_bytes = await _get_max_size_bytes(db, rule.max_size_key)
    if file_size > max_size_bytes:
        raise HTTPException(status_code=413, detail="文件大小超过限制（2MB）")

    allowed_mimes = await _get_allowed_mimes(db, rule.allowed_mimes_key)
    if mime_type.lower() not in allowed_mimes:
        raise HTTPException(status_code=415, detail="不支持的文件格式")

    normalized_hash = file_hash.lower() if file_hash else None
    if normalized_hash:
        duplicate = await media_file_crud.find_active_duplicate(
            db,
            user_id=user.id,
            file_type=file_type,
            file_hash=normalized_hash,
        )
        if duplicate:
            logger.info(
                "media_upload_deduplicated_token",
                user_id=user.id,
                file_type=file_type.name,
                file_id=duplicate.file_id,
            )
            return UploadTokenResult(
                file_id=duplicate.file_id,
                url=build_public_url(duplicate),
                duplicate=True,
            )

    storage_backend = get_storage_backend()
    object_key = generate_object_key(int(file_type), mime_type)
    file_id = generate_file_id()
    original_name_value = original_name or object_key.split("/")[-1]

    record = MediaFile(
        file_id=file_id,
        file_type=int(file_type),
        storage_provider=settings.STORAGE_PROVIDER.lower(),
        bucket_name=settings.TENCENT_COS_BUCKET or None,
        object_key=object_key,
        storage_region=settings.TENCENT_COS_REGION if settings.TENCENT_COS_BUCKET else None,
        original_name=original_name_value,
        file_size=file_size,
        mime_type=mime_type,
        file_hash=normalized_hash,
        is_public=rule.is_public,
        cdn_domain=_determine_cdn_domain(settings),
        upload_by_type=int(UploaderType.USER),
        upload_by_id=user.id,
        upload_by_qiao_id=user.qiao_id,
        status=int(FileStatus.PENDING),
    )

    db.add(record)
    await db.commit()
    await db.refresh(record)

    upload_url = storage_backend.get_presigned_url(
        object_key,
        method="PUT",
        expires_in=timedelta(minutes=5),
        content_type=mime_type,
        content_length=file_size,
    )

    logger.info(
        "media_upload_token_created",
        user_id=user.id,
        file_id=record.file_id,
        file_type=file_type.name,
    )

    return UploadTokenResult(
        file_id=record.file_id,
        upload_url=upload_url,
        object_key=object_key,
        expires_in=300,
        duplicate=False,
    )


async def confirm_upload(
    db: AsyncSession,
    *,
    user: User,
    media: MediaFile,
    etag: str | None,
) -> tuple[MediaFile, bool]:
    """Confirm object exists in storage and finalize record."""

    if media.upload_by_id != user.id:
        raise HTTPException(status_code=403, detail="无权操作")
    if media.status == int(FileStatus.DELETED):
        raise HTTPException(status_code=404, detail="文件不存在")
    if media.status == int(FileStatus.ACTIVE):
        raise HTTPException(status_code=409, detail="文件已确认")

    storage = get_storage_backend()
    try:
        metadata = storage.get_metadata(media.object_key)
    except StorageNotFoundError as exc:
        await _mark_deleted(db, media)
        raise HTTPException(status_code=404, detail="文件不存在") from exc
    except StorageError as exc:
        logger.error(
            "media_storage_metadata_error",
            file_id=media.file_id,
            error=str(exc),
        )
        raise HTTPException(status_code=503, detail="服务暂时不可用，请稍后重试") from exc

    actual_size = int(metadata.get("size", media.file_size))
    if actual_size != media.file_size:
        await _handle_invalid_upload(db, storage, media, reason="size_mismatch")
        raise HTTPException(status_code=400, detail="文件大小不匹配")

    metadata_mime = (metadata.get("content_type") or "").lower()
    if metadata_mime and metadata_mime != media.mime_type.lower():
        await _handle_invalid_upload(db, storage, media, reason="mime_mismatch")
        raise HTTPException(status_code=400, detail="文件类型不匹配")

    metadata_etag = (metadata.get("etag") or metadata.get("ETag") or "").strip('"')
    if etag and metadata_etag and metadata_etag != etag.strip('"'):
        await _handle_invalid_upload(db, storage, media, reason="etag_mismatch")
        raise HTTPException(status_code=400, detail="文件校验失败")

    file_hash = media.file_hash
    if not file_hash:
        try:
            file_bytes = storage.download(media.object_key)
            file_hash = hashlib.sha256(file_bytes).hexdigest()
            media.file_hash = file_hash
        except StorageError as exc:
            logger.error("media_storage_download_error", file_id=media.file_id, error=str(exc))
            raise HTTPException(status_code=503, detail="服务暂时不可用，请稍后重试") from exc

    duplicate = None
    if file_hash:
        duplicate = await media_file_crud.find_active_duplicate(
            db,
            user_id=user.id,
            file_type=FileType(media.file_type),
            file_hash=file_hash,
            exclude_file_id=media.id,
        )

    if duplicate:
        await _handle_duplicate(db, storage, media, duplicate)
        return duplicate, True

    media.status = int(FileStatus.ACTIVE)
    media.etag = metadata_etag or etag
    media.confirmed_at = datetime.now(UTC)
    media.confirmed_by_id = user.id
    db.add(media)
    await db.commit()
    await db.refresh(media)

    logger.info("media_upload_confirmed", file_id=media.file_id, user_id=user.id)
    return media, False


async def _handle_invalid_upload(
    db: AsyncSession,
    storage: StorageBackend,
    media: MediaFile,
    *,
    reason: str,
) -> None:
    logger.warning(
        "media_upload_validation_failed",
        file_id=media.file_id,
        reason=reason,
    )
    try:
        storage.delete(media.object_key)
    except StorageError:
        logger.warning("media_upload_cleanup_failed", file_id=media.file_id)
    await _mark_deleted(db, media)


async def _handle_duplicate(
    db: AsyncSession,
    storage: StorageBackend,
    media: MediaFile,
    duplicate: MediaFile,
) -> None:
    logger.info(
        "media_upload_duplicate_detected",
        new_file_id=media.file_id,
        existing_file_id=duplicate.file_id,
    )
    try:
        storage.delete(media.object_key)
    except StorageError:
        logger.warning("media_upload_duplicate_cleanup_failed", file_id=media.file_id)
    await _mark_deleted(db, media)


async def _mark_deleted(db: AsyncSession, media: MediaFile) -> None:
    media.status = int(FileStatus.DELETED)
    db.add(media)
    await db.commit()


async def _get_allowed_mimes(db: AsyncSession, config_key: str) -> list[str]:
    allowed = await get_config(db, config_key)
    return [item.strip().lower() for item in allowed.split(",") if item.strip()]


async def _get_max_size_bytes(db: AsyncSession, config_key: str) -> int:
    size_mb = int(await get_config(db, config_key))
    return size_mb * 1024 * 1024


def _determine_cdn_domain(settings: Settings) -> str | None:
    local_url = cast(str | None, settings.STORAGE_LOCAL_URL)
    if settings.STORAGE_PROVIDER.lower() == "local":
        return local_url
    return cast(str | None, settings.TENCENT_COS_CDN_DOMAIN) or None
