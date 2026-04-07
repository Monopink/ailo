"""LeanCloud runtime configuration helpers.

Centralizes configuration reads:
- Secrets and stable identifiers come from environment via Settings.
- Runtime-adjustable values come from system_configs via SystemConfigService.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.exceptions import MissingConfigurationError
from app.services.system_config import get_config


def _normalize_optional_str(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    normalized = str(value).strip()
    return normalized or None


def _require_non_empty(value: str | None, *, config_key: str) -> str:
    if value is None or value.strip() == "":
        raise MissingConfigurationError(config_key=config_key)
    return value


@dataclass(frozen=True, slots=True)
class LeanCloudRuntimeConfig:
    app_id: str
    app_key: str
    master_key: str
    base_url: str | None


async def get_leancloud_runtime_config(
    db: AsyncSession,
    *,
    required: bool = True,
) -> LeanCloudRuntimeConfig:
    """Return LeanCloud runtime config from Settings + system_configs."""
    settings = get_settings()
    base_url_raw = await get_config(db, key="leancloud_im_server_url", required=False)
    base_url = _normalize_optional_str(base_url_raw)

    config = LeanCloudRuntimeConfig(
        app_id=settings.LEANCLOUD_IM_APP_ID,
        app_key=settings.LEANCLOUD_IM_APP_KEY,
        master_key=settings.LEANCLOUD_MASTER_KEY,
        base_url=base_url,
    )

    if required and not config.base_url:
        raise MissingConfigurationError(config_key="leancloud_im_server_url")
    if required:
        _require_non_empty(config.app_id, config_key="LEANCLOUD_IM_APP_ID")
        _require_non_empty(config.app_key, config_key="LEANCLOUD_IM_APP_KEY")
        _require_non_empty(config.master_key, config_key="LEANCLOUD_MASTER_KEY")
        _require_non_empty(config.base_url, config_key="leancloud_im_server_url")

    return config


async def get_leancloud_config_status(db: AsyncSession) -> dict[str, bool]:
    """Return status flags for admin UI cards."""
    config = await get_leancloud_runtime_config(db, required=False)
    has_app_id = bool(config.app_id)
    has_master_key = bool(config.master_key)
    has_base_url = bool(config.base_url)
    return {
        "configured": bool(has_app_id and has_master_key and has_base_url),
        "has_app_id": has_app_id,
        "has_master_key": has_master_key,
        "has_base_url": has_base_url,
    }
