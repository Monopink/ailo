"""
Access token cache for WeChat API
"""

import time

from app.utils.logging import get_logger

logger = get_logger(__name__)

# Module-level cache variables
_token: str | None = None
_expires_at: float = 0


def get_token() -> str | None:
    """
    Get cached token

    Returns:
        Cached token if valid, None if expired
    """
    # Check if token expired or will expire in 5 minutes
    if time.time() >= _expires_at - 300:
        logger.warning("Access token expired or will expire soon")
        return None

    return _token


def set_token(token: str, expires_in: int) -> None:
    """
    Set token in cache

    Args:
        token: Access token
        expires_in: Expiry time in seconds (usually 7200)
    """
    global _token, _expires_at
    _token = token
    _expires_at = time.time() + expires_in
    logger.info(f"Access token cached, expires in {expires_in} seconds")


def clear_token() -> None:
    """Clear cached token"""
    global _token, _expires_at
    _token = None
    _expires_at = 0
    logger.info("Access token cache cleared")
