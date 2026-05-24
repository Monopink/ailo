"""Shared helpers for global-unique placeholder key config."""

from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.system_config import SystemConfigService

GLOBAL_UNIQUE_PLACEHOLDER_KEYS_CONFIG_KEY = "ai_global_unique_placeholder_keys"


class _SupportsWarning(Protocol):
    def warning(self, event: str, **kwargs: object) -> object: ...


def normalize_global_unique_placeholder_keys(
    raw_value: object,
    *,
    logger: _SupportsWarning,
    strict_item_type: bool = False,
) -> tuple[list[str], bool]:
    """Normalize raw config value into placeholder keys.

    Returns:
        tuple[list[str], bool]:
            - normalized keys
            - whether config is invalid for caller strategy
    """
    if raw_value is None:
        return [], False
    if not isinstance(raw_value, list):
        logger.warning(
            "invalid_global_unique_placeholder_keys_config",
            config_key=GLOBAL_UNIQUE_PLACEHOLDER_KEYS_CONFIG_KEY,
            reason="config_value is not array",
            value_type=type(raw_value).__name__,
        )
        return [], True

    normalized_keys: list[str] = []
    seen: set[str] = set()
    has_invalid_item = False
    for index, item in enumerate(raw_value):
        if not isinstance(item, str):
            logger.warning(
                "invalid_global_unique_placeholder_keys_item",
                config_key=GLOBAL_UNIQUE_PLACEHOLDER_KEYS_CONFIG_KEY,
                index=index,
                value_type=type(item).__name__,
            )
            has_invalid_item = True
            continue
        key = item.strip()
        if not key or key.startswith("score:") or key in seen:
            continue
        seen.add(key)
        normalized_keys.append(key)

    if strict_item_type and has_invalid_item:
        return [], True
    return normalized_keys, False


async def load_global_unique_placeholder_keys(
    db: AsyncSession,
    *,
    logger: _SupportsWarning,
    strict_item_type: bool = False,
) -> tuple[list[str], bool]:
    """Load and normalize global-unique placeholder key config."""
    raw_value = await SystemConfigService.get_config(
        db, GLOBAL_UNIQUE_PLACEHOLDER_KEYS_CONFIG_KEY, required=False
    )
    return normalize_global_unique_placeholder_keys(
        raw_value,
        logger=logger,
        strict_item_type=strict_item_type,
    )
