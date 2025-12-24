"""
Storage backend factory.
"""

from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.services.storage.base import StorageBackend
from app.services.storage.tencent_cos import TencentCOSBackend


@lru_cache
def get_storage_backend() -> StorageBackend:
    """Return configured storage backend singleton."""
    settings = get_settings()
    if not settings.TENCENT_COS_BUCKET:
        raise ValueError("TENCENT_COS_BUCKET must be configured for COS provider")
    return TencentCOSBackend(
        secret_id=settings.TENCENT_COS_SECRET_ID,
        secret_key=settings.TENCENT_COS_SECRET_KEY,
        region=settings.TENCENT_COS_REGION,
        bucket=settings.TENCENT_COS_BUCKET,
        endpoint=settings.TENCENT_COS_ENDPOINT or None,
        cdn_domain=settings.STORAGE_PUBLIC_DOMAIN or None,
    )
