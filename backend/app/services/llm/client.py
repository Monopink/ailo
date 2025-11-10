"""
Unified LLM client interface.

This module provides high-level functions for interacting with LLM providers
with automatic failover and configuration management.
"""

from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_active_configs
from .providers import factory
from .utils import is_valid_json
from models.llm import LLMConfig, LLMProvider
from utils.logging import get_logger
from exceptions.llm import (
    LLMNoConfigError,
    LLMRequestError,
    LLMTimeoutError,
    ConfigNotVerifiedError,
    JSONSchemaNotSupportedError,
    LLMResponseFormatError,
)

logger = get_logger(__name__)


async def chat_completion(
    db: AsyncSession,
    messages: List[Dict[str, str]],
    json_schema: Optional[Dict[str, Any]] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    thinking_mode: Optional[str] = None,
    name: Optional[str] = None,
    character_request_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Send chat completion request with automatic provider selection and failover.

    Args:
        db: Database session
        messages: List of message objects with 'role' and 'content'
        json_schema: Optional JSON schema for structured output
        temperature: Override temperature setting
        max_tokens: Override max tokens setting
        thinking_mode: Override thinking mode setting (enabled/disabled/auto)
        name: Specific config to use (defaults to primary)
        character_request_params: Character-specific request parameters override

    Returns:
        Dictionary containing response data and metadata
    """
    try:
        # Get configurations to try (primary first, then fallbacks)
        configs_to_try = await _get_configs_to_try(db, name)

        if not configs_to_try:
            raise LLMNoConfigError(config_name=name, details={"requested_name": name})

        # Try each configuration until one succeeds
        last_error = None
        last_error_code = None

        for config, provider in configs_to_try:
            try:
                result = await _call_provider(
                    config,
                    provider,
                    messages,
                    json_schema,
                    temperature,
                    max_tokens,
                    thinking_mode,
                    character_request_params,
                )

                if result["success"]:
                    # Add configuration info to result
                    result["config_used"] = {
                        "name": config.name,
                        "provider_name": provider.name,
                        "model": config.model_name or provider.default_model,
                    }
                    # Ensure request_payload is present
                    if "request_payload" not in result:
                        result["request_payload"] = None
                    return result
                else:
                    last_error = result.get("error", "Unknown error")
                    last_error_code = result.get("error_code", "UNKNOWN")
                    logger.warn(
                        "llm_config_failed",
                        config_name=config.name,
                        provider=provider.name,
                        error=last_error,
                        error_code=last_error_code,
                    )

            except Exception as e:
                last_error = str(e)
                last_error_code = getattr(e, "error_code", "EXCEPTION")
                logger.error(
                    "llm_config_exception",
                    config_name=config.name,
                    provider=provider.name,
                    error=str(e),
                    exc_info=True,
                )

        # All configurations failed
        return {
            "success": False,
            "error": f"All LLM configurations failed. Last error: {last_error}",
            "error_code": last_error_code or "ALL_CONFIGS_FAILED",
            "response": None,
            "usage": None,
            "request_payload": None,
        }

    except LLMNoConfigError as e:
        logger.error("no_llm_config", config_name=name)
        return {
            "success": False,
            "error": str(e),
            "error_code": e.error_code,
            "response": None,
            "usage": None,
            "request_payload": None,
        }

    except Exception as e:
        logger.error("chat_completion_error", error=str(e), exc_info=True)
        return {
            "success": False,
            "error": f"LLM invocation exception: {str(e)}",
            "error_code": "SYSTEM_ERROR",
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
    db: AsyncSession, name: Optional[str]
) -> List[Tuple[LLMConfig, LLMProvider]]:
    """
    Get list of configurations to try in order of priority.

    Applies fallback limit: only configs with priority <= 99 are considered
    to prevent fallback to test/mock configurations in production.
    """
    if name:
        # Use specific configuration (no limit when explicitly requested)
        from .config import get_llm_config

        config_result = await get_llm_config(db, name)
        return [config_result] if config_result else []
    else:
        # Use active configurations with priority limit
        MAX_FALLBACK_PRIORITY = 99  # Exclude test configs (priority >= 100)
        return await get_active_configs(db, max_priority=MAX_FALLBACK_PRIORITY)


async def _call_provider(
    config: LLMConfig,
    provider: LLMProvider,
    messages: List[Dict[str, str]],
    json_schema: Optional[Dict[str, Any]],
    temperature: Optional[float],
    max_tokens: Optional[int],
    thinking_mode: Optional[str],
    character_request_params: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Call the appropriate provider function using factory.

    Parameter priority (highest to lowest):
    1. Explicit parameters (temperature, max_tokens, thinking_mode)
    2. Character-specific overrides (character_request_params from AI Character)
    3. Config defaults (from LLMConfig)
    """
    try:
        # Merge request parameters with priority:
        # 1. Start with character-specific parameters (if provided)
        merged_params = {}
        if character_request_params:
            merged_params.update(character_request_params)
            logger.debug(
                "character_request_params_applied",
                character_params=character_request_params,
                merged_params=merged_params,
            )

        # 2. Apply explicit parameters (highest priority, overrides character params)
        if temperature is not None:
            merged_params["temperature"] = temperature
        if max_tokens is not None:
            merged_params["max_tokens"] = max_tokens
        if thinking_mode is not None:
            merged_params["thinking_mode"] = thinking_mode

        # Extract parameters for factory call
        final_temperature = merged_params.get("temperature")
        final_max_tokens = merged_params.get("max_tokens")
        final_thinking_mode = merged_params.get("thinking_mode")

        result = await factory.chat_completion(
            config=config,
            provider=provider,
            messages=messages,
            json_schema=json_schema,
            temperature=final_temperature,
            max_tokens=final_max_tokens,
            thinking_mode=final_thinking_mode,
            provider_overrides=merged_params.get("provider_overrides"),
        )

        # Wrap result in success format
        return {
            "success": True,
            "response": result["content"],
            "usage": result["usage"],
            "finish_reason": result.get("finish_reason"),
            "model": result.get("model"),
            "raw_response": result.get("raw_response"),  # Pass through raw API response
            "request_payload": result.get("request_params")
            or {
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "thinking_mode": thinking_mode,
                "provider_overrides": merged_params.get("provider_overrides"),
            },
        }

    except (LLMRequestError, LLMTimeoutError) as e:
        return {
            "success": False,
            "error": str(e),
            "error_code": getattr(e, "error_code", "REQUEST_ERROR"),
            "response": None,
            "usage": None,
            "request_payload": None,
        }

    except Exception as e:
        logger.error(f"Unexpected error calling provider: {str(e)}", exc_info=True)
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "error_code": "SYSTEM_ERROR",
            "response": None,
            "usage": None,
            "request_payload": None,
        }


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


async def select_config_for_ai(
    db: AsyncSession, name: Optional[str] = None
) -> Tuple[LLMConfig, LLMProvider]:
    """
    Select and validate LLM config for AI Character usage.

    This function ensures the selected config supports JSON Schema,
    which is required for AI Character functionality.

    Args:
        db: Database session
        name: Specific config to use (defaults to primary)

    Returns:
        Tuple of (config, provider)

    Raises:
        LLMNoConfigError: If no config found
        ConfigNotVerifiedError: If config not verified for JSON Schema support
        JSONSchemaNotSupportedError: If config doesn't support JSON Schema
    """
    from .config import get_llm_config, get_primary_config

    # Get configuration
    if name:
        config_result = await get_llm_config(db, name)
        if not config_result:
            raise LLMNoConfigError(
                config_name=name,
                message=f"配置 '{name}' 不存在或未激活",
                details={"requested_name": name},
            )
    else:
        config_result = await get_primary_config(db)
        if not config_result:
            raise LLMNoConfigError(
                message="没有可用的主配置",
                details={"requested_name": "primary"},
            )

    config, provider = config_result

    # Check JSON Schema support
    if config.json_schema_mode == "auto":
        raise ConfigNotVerifiedError(config_name=config.name)

    if config.json_schema_mode == "disabled":
        raise JSONSchemaNotSupportedError(config_name=config.name)

    # json_schema_mode == 'strict' - can be used
    logger.info(
        "config_selected_for_ai",
        config_name=config.name,
        provider=provider.name,
        json_schema_mode=config.json_schema_mode,
    )

    return config, provider


async def validate_ai_response(
    db: AsyncSession, config: LLMConfig, response_content: str, allow_auto_update: bool = True
) -> None:
    """
    Validate AI response format and optionally auto-update config if needed.

    This function checks if the response is valid JSON. If not and auto-update
    is allowed, it automatically updates the config's json_schema_mode to 'disabled'.

    Args:
        db: Database session
        config: LLM configuration used
        response_content: Response content to validate
        allow_auto_update: Whether to allow automatic config updates (default: True)
                          Set to False in production AI Character usage to prevent
                          accidental config changes.

    Raises:
        LLMResponseFormatError: If response is not valid JSON
    """
    is_json, _ = is_valid_json(response_content)

    if not is_json:
        # Response is not JSON - config status is incorrect
        logger.error(
            "ai_response_format_error",
            config_name=config.name,
            json_schema_mode=config.json_schema_mode,
            response_preview=response_content[:200],
            allow_auto_update=allow_auto_update,
        )

        # Auto-update config status only if allowed
        old_mode = config.json_schema_mode
        if allow_auto_update and config.json_schema_mode != "disabled":
            config.json_schema_mode = "disabled"
            await db.commit()

            logger.warning(
                "config_auto_updated_to_disabled",
                config_name=config.name,
                old_mode=old_mode,
                new_mode="disabled",
            )

        raise LLMResponseFormatError(
            config_name=config.name,
            details={
                "response_preview": response_content[:200],
                "old_json_schema_mode": old_mode,
                "auto_update_allowed": allow_auto_update,
            },
        )
