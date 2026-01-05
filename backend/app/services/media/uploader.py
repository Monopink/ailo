"""
Media upload orchestration (proxy-only flow).
"""

from __future__ import annotations

import hashlib
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
from app.services.system_config import get_config
from app.utils.logging import get_logger

logger = get_logger(__name__)


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
    """Handle backend-proxied uploads using the storage backend directly."""

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
            user_id=user.id,
            actual_size=actual_size,
            file_type=file_type.name,
        )
    elif actual_size != file_size:
        raise HTTPException(status_code=400, detail="文件大小不匹配，请重新选择图片")

    await enforce_daily_quota(db, user_id=user.id, file_type=file_type, file_size=actual_size)

    allowed, _, retry_after = await check_rate_limit(user.qiao_id, "media_upload", db)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="上传过于频繁，请稍后再试",
            headers={"Retry-After": str(retry_after or 60)},
        )

    max_size_bytes = await _get_max_size_bytes(db, rule.max_size_key)
    if actual_size > max_size_bytes:
        raise HTTPException(status_code=413, detail="文件大小超过限制（2MB）")

    allowed_mimes = await _get_allowed_mimes(db, rule.allowed_mimes_key)
    if mime_type.lower() not in allowed_mimes:
        raise HTTPException(status_code=415, detail="不支持的文件格式")

    provided_hash = file_hash.lower() if file_hash else None
    effective_hash = provided_hash or hashlib.sha256(file_bytes).hexdigest()

    duplicate = None
    if effective_hash:
        duplicate = await media_file_crud.find_active_duplicate(
            db,
            user_id=user.id,
            file_type=file_type,
            file_hash=effective_hash,
        )

    if duplicate:
        logger.info(
            "media_proxy_upload_deduplicated",
            user_id=user.id,
            file_type=file_type.name,
            file_id=duplicate.file_id,
        )
        return duplicate, True

    storage = get_storage_backend()
    object_key = generate_object_key(int(file_type), mime_type)
    file_id = generate_file_id()
    original_name_value = original_name or object_key.split("/")[-1]

    metadata = {"content_type": mime_type, "uploaded_via": "proxy"}
    try:
        # Call storage.upload() directly - boto3 is thread-safe in uvicorn worker
        storage.upload(
            object_key,
            file_bytes,
            mime_type,
            metadata=metadata,
            is_public=rule.is_public,
        )
    except StorageError as exc:
        logger.error("media_proxy_upload_failed", error=str(exc))
        raise HTTPException(status_code=503, detail="上传失败，请稍后再试") from exc

    record = MediaFile(
        file_id=file_id,
        file_type=int(file_type),
        storage_provider=storage.provider_name,
        bucket_name=settings.TENCENT_COS_BUCKET or None,
        object_key=object_key,
        storage_region=settings.TENCENT_COS_REGION if settings.TENCENT_COS_BUCKET else None,
        original_name=original_name_value,
        file_size=actual_size,
        mime_type=mime_type,
        file_hash=effective_hash,
        is_public=rule.is_public,
        upload_by_type=int(UploaderType.USER),
        upload_by_id=user.id,
        upload_by_qiao_id=user.qiao_id,
        status=int(FileStatus.ACTIVE),
        confirmed_at=datetime.now(UTC),
        confirmed_by_id=user.id,
    )

    db.add(record)
    await db.commit()
    await db.refresh(record)

    logger.info("media_proxy_upload_succeeded", file_id=record.file_id, user_id=user.id)
    return record, False


async def _get_allowed_mimes(db: AsyncSession, config_key: str) -> list[str]:
    allowed = await get_config(db, config_key)
    return [item.strip().lower() for item in allowed.split(",") if item.strip()]


async def _get_max_size_bytes(db: AsyncSession, config_key: str) -> int:
    size_mb = int(await get_config(db, config_key))
    return size_mb * 1024 * 1024
