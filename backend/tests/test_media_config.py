import pytest

from app.core.config import get_settings
from app.crud.system import system_configs
from app.services.media.config import (
    clear_media_base_url_cache,
    get_media_base_url,
    get_media_base_url_source,
    refresh_media_base_url,
)
from app.services.system_config import SystemConfigService


@pytest.mark.asyncio
async def test_refresh_media_base_url_uses_db_value(db_session):
    """Runtime CDN domain should prefer system_configs value."""
    await system_configs.update_config_value(
        db_session,
        config_key="media_public_base_url",
        config_value="https://cdn-from-db.example.com",
        updated_by=None,
        validate_enum=False,
    )
    await SystemConfigService.reload_cache(db_session)
    clear_media_base_url_cache()

    value = await refresh_media_base_url(db_session)

    assert value == "https://cdn-from-db.example.com"
    assert get_media_base_url() == "https://cdn-from-db.example.com"
    assert get_media_base_url_source() == "system_configs"


@pytest.mark.asyncio
async def test_refresh_media_base_url_env_fallback(monkeypatch, db_session):
    """Fallback to environment variable when DB config is blank."""
    await system_configs.update_config_value(
        db_session,
        config_key="media_public_base_url",
        config_value="",
        updated_by=None,
        validate_enum=False,
    )
    await SystemConfigService.reload_cache(db_session)

    settings = get_settings()
    monkeypatch.setattr(
        settings,
        "MEDIA_PUBLIC_BASE_URL",
        "https://cdn-from-env.example.com",
        raising=False,
    )
    clear_media_base_url_cache()

    value = await refresh_media_base_url(db_session)

    assert value == "https://cdn-from-env.example.com"
    assert get_media_base_url() == "https://cdn-from-env.example.com"
    assert get_media_base_url_source() == "env"
