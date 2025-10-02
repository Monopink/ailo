"""
LLM service utility functions.

This module provides common utility functions for LLM providers.
"""

import os
import json
from typing import Optional, Tuple, Any

from models.llm import LLMProvider
from utils.logging import get_logger

logger = get_logger(__name__)


def get_provider_api_key(provider: LLMProvider) -> str:
    """
    Get API key for LLM provider using naming convention.

    Convention: {PROVIDER_NAME}_API_KEY
    Example: DOUBAO_API_KEY, OPENAI_API_KEY, CLAUDE_API_KEY

    Args:
        provider: LLM provider instance

    Returns:
        API key string

    Raises:
        ValueError: If API key not found in environment
    """
    env_key = f"{provider.name.upper()}_API_KEY"
    api_key = os.getenv(env_key)

    if not api_key:
        logger.error(
            "api_key_not_found",
            provider_name=provider.name,
            env_key=env_key,
        )
        raise ValueError(f"API key not found in environment: {env_key}")

    logger.debug(
        "api_key_retrieved",
        provider_name=provider.name,
        env_key=env_key,
    )

    return api_key


def get_provider_base_url(provider: LLMProvider) -> Optional[str]:
    """
    Get base URL for LLM provider.

    Can be overridden by environment variable: {PROVIDER_NAME}_BASE_URL

    Args:
        provider: LLM provider instance

    Returns:
        Base URL string or None
    """
    # Check environment variable first
    env_key = f"{provider.name.upper()}_BASE_URL"
    env_url = os.getenv(env_key)

    if env_url:
        logger.debug(
            "base_url_from_env",
            provider_name=provider.name,
            env_key=env_key,
        )
        return env_url

    # Fall back to database configuration
    return provider.base_url


def is_valid_json(content: str) -> Tuple[bool, Optional[Any]]:
    """
    Check if content is valid JSON and parse it.

    Args:
        content: String content to check

    Returns:
        Tuple of (is_valid, parsed_data)
        - is_valid: True if content is valid JSON
        - parsed_data: Parsed JSON data if valid, None otherwise
    """
    if not content or not isinstance(content, str):
        return False, None

    try:
        parsed = json.loads(content)
        return True, parsed
    except (json.JSONDecodeError, ValueError):
        return False, None
