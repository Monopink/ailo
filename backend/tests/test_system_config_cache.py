"""Tests for system configuration cache miss behavior."""

from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import MissingConfigurationError
from app.services import system_config as system_config_module
from app.services.system_config import SystemConfigService


@pytest.fixture(autouse=True)
def _restore_config_state() -> Generator[None, None, None]:
    """Restore global config cache state after each test."""
    original_cache = dict(system_config_module._config_state["cache"])
    original_loaded = system_config_module._config_state["loaded"]
    original_last_version_check_at = system_config_module._config_state["last_version_check_at"]
    try:
        yield
    finally:
        system_config_module._config_state["cache"].clear()
        system_config_module._config_state["cache"].update(original_cache)
        system_config_module._config_state["loaded"] = original_loaded
        system_config_module._config_state["last_version_check_at"] = original_last_version_check_at


@pytest.mark.asyncio
async def test_get_config_cache_miss_reads_db_and_backfills_cache(
    db_session: AsyncSession,
) -> None:
    """A cache miss should fetch one key from database and backfill cache."""
    config_key = "test_system_config_cache_miss_db_hit"
    await db_session.execute(
        text(
            """
            INSERT INTO system_configs
                (
                    config_key,
                    config_value,
                    default_value,
                    value_type,
                    config_shape,
                    config_scope,
                    description,
                    group_name,
                    allowed_values
                )
            VALUES
                (
                    :config_key,
                    'true'::jsonb,
                    'true'::jsonb,
                    3,
                    1,
                    'system',
                    'test cache miss db hit',
                    'test',
                    NULL
                )
            ON CONFLICT (config_key)
            DO UPDATE SET
                config_value = EXCLUDED.config_value,
                default_value = EXCLUDED.default_value,
                value_type = EXCLUDED.value_type,
                config_shape = EXCLUDED.config_shape,
                config_scope = EXCLUDED.config_scope,
                description = EXCLUDED.description,
                group_name = EXCLUDED.group_name,
                allowed_values = EXCLUDED.allowed_values
            """
        ),
        {"config_key": config_key},
    )
    await db_session.flush()

    system_config_module._config_state["cache"].clear()
    system_config_module._config_state["loaded"] = True

    value = await SystemConfigService.get_config(db_session, config_key, required=True)

    assert value is True
    assert system_config_module._config_state["cache"][config_key] is True


@pytest.mark.asyncio
async def test_get_config_cache_miss_db_miss_still_raises(
    db_session: AsyncSession,
) -> None:
    """A true miss should still raise MissingConfigurationError for required keys."""
    missing_key = "test_system_config_cache_miss_db_miss"

    system_config_module._config_state["cache"].clear()
    system_config_module._config_state["loaded"] = True

    with pytest.raises(MissingConfigurationError):
        await SystemConfigService.get_config(db_session, missing_key, required=True)


@pytest.mark.asyncio
async def test_get_config_auto_reload_on_updated_timestamp(
    db_session: AsyncSession,
) -> None:
    """Cache should auto reload when a newer system_configs.updated_at is detected."""
    config_key = "test_system_config_auto_reload"
    await db_session.execute(
        text(
            """
            INSERT INTO system_configs
                (
                    config_key,
                    config_value,
                    default_value,
                    value_type,
                    config_shape,
                    config_scope,
                    description,
                    group_name,
                    allowed_values
                )
            VALUES
                (
                    :config_key,
                    '10'::jsonb,
                    '10'::jsonb,
                    2,
                    1,
                    'system',
                    'test auto reload',
                    'test',
                    NULL
                )
            ON CONFLICT (config_key)
            DO UPDATE SET
                config_value = EXCLUDED.config_value,
                updated_at = NOW()
            """
        ),
        {"config_key": config_key},
    )
    await db_session.flush()

    system_config_module._config_state["cache"].clear()
    system_config_module._config_state["loaded"] = False

    value_before = await SystemConfigService.get_config_int(db_session, config_key, required=True)
    assert value_before == 10

    await db_session.execute(
        text(
            """
            UPDATE system_configs
            SET
                config_value = '25'::jsonb,
                updated_at = NOW() + interval '1 second'
            WHERE config_key = :config_key
            """
        ),
        {"config_key": config_key},
    )
    await db_session.flush()

    system_config_module._config_state["last_version_check_at"] = datetime.now(UTC) - timedelta(
        seconds=10
    )

    value_after = await SystemConfigService.get_config_int(db_session, config_key, required=True)
    assert value_after == 25
