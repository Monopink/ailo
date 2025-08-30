"""
LLM configuration functions.

This module provides functions for retrieving LLM configurations.
"""

from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from crud.llm import llm_config, llm_provider
from models.llm import LLMConfig, LLMProvider


async def get_llm_config(db: AsyncSession, config_key: str) -> Optional[Tuple[LLMConfig, LLMProvider]]:
    """
    Get LLM configuration and provider by config key.

    Args:
        db: Database session
        config_key: Configuration key (e.g., 'primary', 'backup')

    Returns:
        Tuple of (config, provider) or None if not found
    """
    config = await llm_config.get_by_config_key(db, config_key=config_key)
    if not config or not config.is_active:
        return None

    provider = await llm_provider.get(db, id=config.provider_id)
    if not provider or provider.status != 1:
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
    if not provider or provider.status != 1:
        return None

    return config, provider


async def get_active_configs(db: AsyncSession) -> List[Tuple[LLMConfig, LLMProvider]]:
    """
    Get all active LLM configurations ordered by priority.

    Args:
        db: Database session

    Returns:
        List of (config, provider) tuples ordered by priority
    """
    configs = await llm_config.get_configs_by_priority(db, active_only=True)
    result = []

    for config in configs:
        provider = await llm_provider.get(db, id=config.provider_id)
        if provider and provider.status == 1:
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
    if not provider or provider.status != 1:
        return None

    configs = await llm_config.get_active_configs(db, provider_id=provider.id)
    if not configs:
        return None

    # Return the highest priority config
    config = min(configs, key=lambda c: c.priority)
    return config, provider
