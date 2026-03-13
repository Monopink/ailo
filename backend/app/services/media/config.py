"""
Runtime helpers for media-related configuration.

Provides cached access to ``media_public_base_url`` with system_configs as the
authoritative source.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import MissingConfigurationError
from app.services.system_config import SystemConfigService
from app.utils.logging import get_logger

logger = get_logger(__name__)

_MEDIA_BASE_URL_KEY: Final = "media_public_base_url"


@dataclass(slots=True)
class _MediaBaseUrlState:
    value: str | None = None
    source: str = "unset"


_state = _MediaBaseUrlState()
_lock: Final = asyncio.Lock()


def _normalize(value: str | None) -> str | None:
    """Normalize CDN/COS base URL by stripping spaces and trailing slash."""
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return normalized.rstrip("/")


async def refresh_media_base_url(db: AsyncSession) -> str:
    """
    Refresh cached media base URL from system_configs.

    Args:
        db: Active AsyncSession for reading system_configs.

    Returns:
        Normalized CDN/COS base URL.
    """
    async with _lock:
        db_value = await SystemConfigService.get_config(db, _MEDIA_BASE_URL_KEY, required=False)
        normalized = (
            _normalize(db_value if isinstance(db_value, str) else str(db_value))
            if db_value is not None
            else None
        )
        source = "system_configs"

        if not normalized:
            logger.error(
                "media_public_base_url_missing",
                source="system_configs",
            )
            raise MissingConfigurationError(config_key=_MEDIA_BASE_URL_KEY)

        _state.value = normalized
        _state.source = source
        logger.info(
            "media_public_base_url_loaded",
            source=source,
            config_key=_MEDIA_BASE_URL_KEY,
        )
        return normalized


def get_media_base_url() -> str:
    """
    Return cached media base URL.

    Raises MissingConfigurationError if refresh has not been executed yet.
    """
    if _state.value:
        return _state.value

    logger.error(
        "media_public_base_url_cache_uninitialized",
        config_key=_MEDIA_BASE_URL_KEY,
    )
    raise MissingConfigurationError(config_key=_MEDIA_BASE_URL_KEY)


def clear_media_base_url_cache() -> None:
    """Reset cached media base URL (used before reload)."""
    _state.value = None
    _state.source = "unset"


def get_media_base_url_source() -> str:
    """Return the current data source for the cached base URL."""
    return _state.source
