"""
Storage backend factory.
"""

from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.services.storage.base import StorageBackend
from app.services.storage.local import LocalStorageBackend
from app.services.storage.tencent_cos import TencentCOSBackend


@lru_cache
def get_storage_backend() -> StorageBackend:
    """Return configured storage backend singleton."""
    settings = get_settings()
    provider = settings.STORAGE_PROVIDER.lower()
    if provider == "local":
        return LocalStorageBackend(
            base_path=settings.STORAGE_LOCAL_PATH,
            base_url=settings.STORAGE_LOCAL_URL,
        )
    if provider == "tencent_cos":
        if not settings.TENCENT_COS_BUCKET:
            raise ValueError("TENCENT_COS_BUCKET must be configured for COS provider")
        return TencentCOSBackend(
            secret_id=settings.TENCENT_COS_SECRET_ID,
            secret_key=settings.TENCENT_COS_SECRET_KEY,
            region=settings.TENCENT_COS_REGION,
            bucket=settings.TENCENT_COS_BUCKET,
            endpoint=settings.TENCENT_COS_ENDPOINT or None,
            cdn_domain=settings.TENCENT_COS_CDN_DOMAIN or None,
        )
    raise ValueError(f"Unsupported storage provider: {provider}")
