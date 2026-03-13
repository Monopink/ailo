import pytest
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.system import system_configs
from app.exceptions import MissingConfigurationError
from app.services.media.config import (
    clear_media_base_url_cache,
    get_media_base_url,
    get_media_base_url_source,
    refresh_media_base_url,
)
from app.services.system_config import SystemConfigService


@pytest.mark.asyncio
async def test_refresh_media_base_url_uses_db_value(db_session: AsyncSession) -> None:
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
async def test_refresh_media_base_url_missing_raises(db_session: AsyncSession) -> None:
    """Missing system_configs value should raise without fallback."""
    await system_configs.update_config_value(
        db_session,
        config_key="media_public_base_url",
        config_value="",
        updated_by=None,
        validate_enum=False,
    )
    await SystemConfigService.reload_cache(db_session)
    clear_media_base_url_cache()
    with pytest.raises(MissingConfigurationError):
        await refresh_media_base_url(db_session)
    assert get_media_base_url_source() == "unset"
    with pytest.raises(MissingConfigurationError):
        get_media_base_url()
