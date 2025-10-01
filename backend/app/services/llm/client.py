"""
Unified LLM client interface.

This module provides high-level functions for interacting with LLM providers
with automatic failover and configuration management.
"""

from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_active_configs
from .providers import PROVIDER_REGISTRY
from models.llm import LLMConfig, LLMProvider
from utils.logging import get_logger

logger = get_logger(__name__)


async def chat_completion(
    db: AsyncSession,
    messages: List[Dict[str, str]],
    json_schema: Optional[Dict[str, Any]] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    enable_thinking: Optional[bool] = None,
    config_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Send chat completion request with automatic provider selection and failover.

    Args:
        db: Database session
        messages: List of message objects with 'role' and 'content'
        json_schema: Optional JSON schema for structured output
        temperature: Override temperature setting
        max_tokens: Override max tokens setting
        enable_thinking: Override thinking mode setting
        config_key: Specific config to use (defaults to primary)

    Returns:
        Dictionary containing response data and metadata
    """
    try:
        # Get configurations to try (primary first, then fallbacks)
        configs_to_try = await _get_configs_to_try(db, config_key)

        if not configs_to_try:
            return {
                "success": False,
                "error": "No active LLM configurations found",
                "response": None,
                "usage": None,
                "request_payload": None,
            }

        # Try each configuration until one succeeds
        last_error = None
        for config, provider in configs_to_try:
            try:
                result = await _call_provider(
                    config, provider, messages, json_schema, temperature, max_tokens, enable_thinking
                )

                if result["success"]:
                    # Add configuration info to result
                    result["config_used"] = {
                        "config_key": config.config_key,
                        "provider_name": provider.name,
                        "model": config.model_name or provider.default_model,
                    }
                    # Ensure request_payload is present
                    if "request_payload" not in result:
                        result["request_payload"] = None
                    return result
                else:
                    last_error = result["error"]
                    logger.warning(
                        "llm_config_failed",
                        config_key=config.config_key,
                        provider=provider.name,
                        error=result["error"],
                    )

            except Exception as e:
                last_error = str(e)
                logger.warning(
                    "llm_config_exception",
                    config_key=config.config_key,
                    provider=provider.name,
                    error=str(e),
                )

        # All configurations failed
        return {
            "success": False,
            "error": f"All LLM configurations failed. Last error: {last_error}",
            "response": None,
            "usage": None,
            "request_payload": None,
        }

    except Exception as e:
        logger.error("chat_completion_error", error=str(e))
        return {
            "success": False,
            "error": str(e),
            "response": None,
            "usage": None,
            "request_payload": None,
        }


async def get_primary_llm_config(db: AsyncSession) -> Optional[Tuple[LLMConfig, LLMProvider]]:
    """
    Get primary LLM configuration.

    Args:
        db: Database session

    Returns:
        Tuple of (config, provider) or None if not found
    """
    from .config import get_primary_config as _get_primary_config

    return await _get_primary_config(db)


async def _get_configs_to_try(
    db: AsyncSession, config_key: Optional[str]
) -> List[Tuple[LLMConfig, LLMProvider]]:
    """Get list of configurations to try in order of priority."""
    if config_key:
        # Use specific configuration
        from .config import get_llm_config

        config_result = await get_llm_config(db, config_key)
        return [config_result] if config_result else []
    else:
        # Use all active configurations ordered by priority
        return await get_active_configs(db)


async def _call_provider(
    config: LLMConfig,
    provider: LLMProvider,
    messages: List[Dict[str, str]],
    json_schema: Optional[Dict[str, Any]],
    temperature: Optional[float],
    max_tokens: Optional[int],
    enable_thinking: Optional[bool],
) -> Dict[str, Any]:
    """Call the appropriate provider function."""
    provider_func = PROVIDER_REGISTRY.get(provider.name)

    if not provider_func:
        return {
            "success": False,
            "error": f"Unsupported provider: {provider.name}",
            "response": None,
            "usage": None,
            "request_payload": None,
        }

    return await provider_func(
        config, provider, messages, json_schema, temperature, max_tokens, enable_thinking
    )


# Convenience function for specific provider
async def chat_completion_with_provider(
    db: AsyncSession,
    provider_name: str,
    messages: List[Dict[str, str]],
    json_schema: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> Dict[str, Any]:
    """Send chat completion request to a specific provider."""
    from .config import get_config_by_provider

    config_result = await get_config_by_provider(db, provider_name)

    if not config_result:
        return {
            "success": False,
            "error": f"{provider_name.title()} configuration not found or inactive",
            "response": None,
            "usage": None,
            "request_payload": None,
        }

    config, provider = config_result
    return await _call_provider(config, provider, messages, json_schema, **kwargs)
