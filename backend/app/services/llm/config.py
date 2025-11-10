"""
LLM configuration functions.

This module provides functions for retrieving LLM configurations.
"""

from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from crud.llm import llm_config, llm_provider
from models.llm import LLMConfig, LLMProvider


async def get_llm_config(
    db: AsyncSession, name: Optional[str] = None, config_id: Optional[int] = None
) -> Optional[Tuple[LLMConfig, LLMProvider]]:
    """
    Get LLM configuration and provider by config key or ID.

    Args:
        db: Database session
        name: Configuration name (e.g., 'primary', 'backup')
        config_id: Configuration ID

    Returns:
        Tuple of (config, provider) or None if not found
    """
    if name:
        config = await llm_config.get_by_name(db, name=name)
    elif config_id:
        config = await llm_config.get(db, id=config_id)
    else:
        return None

    if not config:
        return None

    provider = await llm_provider.get(db, id=config.provider_id)
    if not provider:
        return None

    return config, provider


async def get_primary_config(db: AsyncSession) -> Optional[Tuple[LLMConfig, LLMProvider]]:
    """
    Get primary LLM configuration.

    Args:
        db: Database session

    Returns:
        Tuple of (config, provider) or None if not found
    """
    config = await llm_config.get_primary_config(db)
    if not config:
        return None

    provider = await llm_provider.get(db, id=config.provider_id)
    if not provider:
        return None

    return config, provider


async def get_active_configs(
    db: AsyncSession, max_priority: Optional[int] = None
) -> List[Tuple[LLMConfig, LLMProvider]]:
    """
    Get all active LLM configurations ordered by priority.

    Args:
        db: Database session
        max_priority: Maximum priority threshold (configs with priority > max_priority are excluded)
                     Default: None (no limit)
                     Recommended: 99 (excludes test/mock configs with priority >= 100)

    Returns:
        List of (config, provider) tuples ordered by priority

    Priority Convention:
        1-10:   Production primary configs
        11-50:  Production backup configs
        51-99:  Development/staging configs
        100+:   Test/mock configs (excluded from automatic fallback when max_priority=99)
    """
    configs = await llm_config.get_configs_by_priority(db, active_only=True)

    # Apply priority threshold
    if max_priority is not None:
        configs = [c for c in configs if c.priority <= max_priority]

    result = []
    for config in configs:
        provider = await llm_provider.get(db, id=config.provider_id)
        if provider:
            result.append((config, provider))

    return result


async def get_config_by_provider(
    db: AsyncSession, provider_name: str
) -> Optional[Tuple[LLMConfig, LLMProvider]]:
    """
    Get active configuration for a specific provider.

    Args:
        db: Database session
        provider_name: Provider name (e.g., 'doubao', 'openai')

    Returns:
        Tuple of (config, provider) or None if not found
    """
    provider = await llm_provider.get_by_name(db, name=provider_name)
    if not provider:
        return None

    configs = await llm_config.get_active_configs(db, provider_id=provider.id)
    if not configs:
        return None

    # Return the highest priority config
    config = min(configs, key=lambda c: c.priority)
    return config, provider
