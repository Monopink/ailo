"""Access token cache for WeChat API."""

import time
from typing import TypedDict

from app.utils.logging import get_logger

logger = get_logger(__name__)


class _TokenCache(TypedDict):
    token: str | None
    expires_at: float


# Module-level cache variables
_token_cache: _TokenCache = {"token": None, "expires_at": 0.0}


def get_token() -> str | None:
    """
    Get cached token.

    Returns:
        Cached token if valid, None if expired
    """
    expires_at = _token_cache["expires_at"]
    # Check if token expired or will expire in 5 minutes
    if time.time() >= expires_at - 300:
        logger.warning("Access token expired or will expire soon")
        return None

    return _token_cache["token"]


def set_token(token: str, expires_in: int) -> None:
    """
    Set token in cache.

    Args:
        token: Access token
        expires_in: Expiry time in seconds (usually 7200)
    """
    _token_cache["token"] = token
    _token_cache["expires_at"] = time.time() + expires_in
    logger.info(f"Access token cached, expires in {expires_in} seconds")


def clear_token() -> None:
    """Clear cached token."""
    _token_cache["token"] = None
    _token_cache["expires_at"] = 0.0
    logger.info("Access token cache cleared")
