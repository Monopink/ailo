"""
Temporary code manager for phone binding fallback
"""

import secrets
import time

from app.utils.logging import get_logger

logger = get_logger(__name__)

# Module-level storage: code -> (openid, expires_at)
_codes: dict[str, tuple[str, float]] = {}


def generate_code(openid: str) -> str:
    """
    Generate temporary code for openid

    Args:
        openid: WeChat openid

    Returns:
        Temporary code (32 characters)
    """
    # Generate secure random code
    code = secrets.token_urlsafe(24)

    # Store with 5 minutes expiry
    expires_at = time.time() + 300
    _codes[code] = (openid, expires_at)

    logger.info(f"Generated temp code for openid: {openid[:8]}...")

    # Clean up expired codes
    _cleanup_codes()

    return code


def verify_code(code: str) -> str | None:
    """
    Verify code and return openid

    Args:
        code: Temporary code

    Returns:
        openid if valid, None if invalid or expired
    """
    if code not in _codes:
        logger.warning(f"Invalid temp code: {code[:8]}...")
        return None

    openid, expires_at = _codes[code]

    # Check expiry
    if time.time() >= expires_at:
        logger.warning(f"Expired temp code: {code[:8]}...")
        del _codes[code]
        return None

    # One-time use: remove after verification
    del _codes[code]
    logger.info(f"Verified temp code for openid: {openid[:8]}...")

    return openid


def _cleanup_codes() -> None:
    """Clean up expired codes"""
    now = time.time()
    expired_codes = [code for code, (_, expires_at) in _codes.items() if now >= expires_at]

    for code in expired_codes:
        del _codes[code]

    if expired_codes:
        logger.info(f"Cleaned up {len(expired_codes)} expired temp codes")
