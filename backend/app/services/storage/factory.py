"""
Storage backend factory.
"""

from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.services.media.config import get_media_base_url
from app.services.storage.base import StorageBackend
from app.services.storage.tencent_cos import TencentCOSBackend


@lru_cache
def get_storage_backend() -> StorageBackend:
    """Return cached storage backend instance."""
    settings = get_settings()
    if not settings.TENCENT_COS_BUCKET:
        raise ValueError("TENCENT_COS_BUCKET must be configured for COS provider")
    cdn_domain = get_media_base_url()
    return TencentCOSBackend(
        secret_id=settings.TENCENT_COS_SECRET_ID,
        secret_key=settings.TENCENT_COS_SECRET_KEY,
        region=settings.TENCENT_COS_REGION,
        bucket=settings.TENCENT_COS_BUCKET,
        endpoint=settings.TENCENT_COS_ENDPOINT or None,
        cdn_domain=cdn_domain,
    )


def reload_storage_backend() -> StorageBackend:
    """Clear cached storage backend and return a re-initialized instance."""
    get_storage_backend.cache_clear()
    return get_storage_backend()
