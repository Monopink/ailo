"""
Media upload quota enforcement.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.message import media_file as media_file_crud
from app.enums import FileType
from app.services.media.rules import get_file_type_rule
from app.services.system_config import get_config_int
from app.utils.logging import get_logger

logger = get_logger(__name__)


async def enforce_daily_quota(
    db: AsyncSession, *, user_id: int, file_type: FileType, file_size: int
) -> None:
    """
    Ensure user has not exceeded daily upload quota for specific file type.

    Raises:
        HTTPException: 400/429 when quota exceeded or type unsupported.
    """

    rule = get_file_type_rule(file_type)
    if not rule:
        raise HTTPException(status_code=400, detail="当前仅支持头像上传")

    daily_quota = await get_config_int(db, rule.daily_quota_key)
    daily_size_limit_mb = await get_config_int(db, rule.daily_size_quota_key)
    daily_size_limit_bytes = daily_size_limit_mb * 1024 * 1024

    day_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    current_count, current_size = await media_file_crud.get_daily_usage(
        db, user_id=user_id, file_type=file_type, day_start=day_start
    )

    if current_count >= daily_quota:
        logger.warning(
            "media_daily_count_quota_exceeded",
            user_id=user_id,
            file_type=file_type.name,
            quota=daily_quota,
        )
        raise HTTPException(status_code=429, detail="今日上传次数已达上限")

    if current_size + file_size > daily_size_limit_bytes:
        logger.warning(
            "media_daily_size_quota_exceeded",
            user_id=user_id,
            file_type=file_type.name,
            size_limit=daily_size_limit_bytes,
            attempted=current_size + file_size,
        )
        raise HTTPException(status_code=429, detail="今日上传大小已达上限")
