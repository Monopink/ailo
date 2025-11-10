"""
Authentication Failure Tracker

Tracks authentication failures for lockout and CAPTCHA triggering.
"""

from typing import Dict, Tuple, Optional
from collections import deque
from sqlalchemy.ext.asyncio import AsyncSession
import time

from services.system_config import get_config
from utils.logging import get_logger

logger = get_logger(__name__)

# Global cache for failure tracking
_failure_cache: Dict[str, Dict] = {}


async def record_auth_failure(
    identifier: str, auth_type: str, db: AsyncSession  # IP or user_id  # 'admin_auth' or 'user_auth'
) -> None:
    """
    Record authentication failure.

    Args:
        identifier: IP address or user ID
        auth_type: Authentication type
        db: Database session
    """
    cache_key = f"{auth_type}:{identifier}"
    now = time.time()

    # Initialize cache for this key if not exists
    if cache_key not in _failure_cache:
        _failure_cache[cache_key] = {"failures": deque(), "locked_until": None}

    # Record failure
    _failure_cache[cache_key]["failures"].append(now)

    # Get lockout configuration
    max_failures = int(await get_config(db, key=f"{auth_type}_max_failures"))
    lockout_duration = int(await get_config(db, key=f"{auth_type}_lockout_duration"))

    # Clean old failures (outside lockout window)
    while (
        _failure_cache[cache_key]["failures"]
        and _failure_cache[cache_key]["failures"][0] < now - lockout_duration
    ):
        _failure_cache[cache_key]["failures"].popleft()

    # Check if should lock
    failure_count = len(_failure_cache[cache_key]["failures"])

    if failure_count >= max_failures:
        # Lock the identifier
        _failure_cache[cache_key]["locked_until"] = now + lockout_duration

        logger.warning(
            "auth_identifier_locked",
            identifier=identifier,
            auth_type=auth_type,
            failure_count=failure_count,
            locked_until=_failure_cache[cache_key]["locked_until"],
        )
    else:
        logger.info(
            "auth_failure_recorded",
            identifier=identifier,
            auth_type=auth_type,
            failure_count=failure_count,
            max_failures=max_failures,
        )


async def check_lockout(identifier: str, auth_type: str, db: AsyncSession) -> Tuple[bool, Optional[int]]:
    """
    Check if identifier is locked out.

    Args:
        identifier: IP address or user ID
        auth_type: Authentication type
        db: Database session

    Returns:
        (is_locked, remaining_seconds)
    """
    # Check whitelist first
    whitelist_str = await get_config(db, key=f"{auth_type}_whitelist", required=False) or ""

    if whitelist_str:
        whitelist = [ip.strip() for ip in whitelist_str.split(",")]
        if identifier in whitelist:
            logger.debug("auth_whitelist_allowed", identifier=identifier, auth_type=auth_type)
            return False, None

    cache_key = f"{auth_type}:{identifier}"
    now = time.time()

    # Check if locked
    if cache_key in _failure_cache:
        locked_until = _failure_cache[cache_key].get("locked_until")

        if locked_until and locked_until > now:
            remaining = int(locked_until - now) + 1

            logger.warning(
                "auth_identifier_locked_check",
                identifier=identifier,
                auth_type=auth_type,
                remaining_seconds=remaining,
            )

            return True, remaining

        # Clear lock if expired
        if locked_until and locked_until <= now:
            _failure_cache[cache_key]["locked_until"] = None
            logger.info("auth_lock_expired", identifier=identifier, auth_type=auth_type)

    return False, None


async def should_require_captcha(identifier: str, auth_type: str, db: AsyncSession) -> bool:
    """
    Check if CAPTCHA is required.

    Args:
        identifier: IP address or user ID
        auth_type: Authentication type
        db: Database session

    Returns:
        True if CAPTCHA is required
    """
    # Check if CAPTCHA is enabled
    captcha_provider = await get_config(
        db,
        key=f"{auth_type.split('_')[0]}_captcha_provider",  # Extract 'admin' or 'user'
        required=False,
    )

    if captcha_provider is None or captcha_provider == "none":
        return False

    # Get threshold
    threshold = int(await get_config(db, key=f"{auth_type.split('_')[0]}_captcha_threshold"))

    cache_key = f"{auth_type}:{identifier}"
    now = time.time()

    # Check failure count
    if cache_key in _failure_cache:
        failures = _failure_cache[cache_key]["failures"]

        # Clean old failures (last 30 minutes)
        while failures and failures[0] < now - 1800:
            failures.popleft()

        failure_count = len(failures)

        if failure_count >= threshold:
            logger.info(
                "captcha_required",
                identifier=identifier,
                auth_type=auth_type,
                failure_count=failure_count,
                threshold=threshold,
            )
            return True

    return False


async def reset_failures(identifier: str, auth_type: str) -> None:
    """
    Reset failure count after successful authentication.

    Args:
        identifier: IP address or user ID
        auth_type: Authentication type
    """
    cache_key = f"{auth_type}:{identifier}"

    if cache_key in _failure_cache:
        _failure_cache[cache_key]["failures"].clear()
        _failure_cache[cache_key]["locked_until"] = None

        logger.info("auth_failures_reset", identifier=identifier, auth_type=auth_type)


def cleanup_auth_tracker_cache() -> None:
    """
    Clean up auth tracker cache.

    Removes entries with no recent failures.
    Should be called periodically.
    """
    global _failure_cache

    now = time.time()
    keys_to_remove = []

    for key, data in _failure_cache.items():
        failures = data["failures"]

        # Clean old failures (older than 1 hour)
        while failures and failures[0] < now - 3600:
            failures.popleft()

        # Mark key for removal if no recent failures and not locked
        if not failures and (not data["locked_until"] or data["locked_until"] <= now):
            keys_to_remove.append(key)

    # Remove marked keys
    for key in keys_to_remove:
        del _failure_cache[key]

    if keys_to_remove:
        logger.info(
            "auth_tracker_cache_cleaned",
            removed_keys_count=len(keys_to_remove),
            remaining_keys_count=len(_failure_cache),
        )
