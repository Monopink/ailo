"""
Authentication Failure Tracker

Tracks authentication failures for lockout and CAPTCHA triggering.
"""

import time
from collections import deque
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.system_config import get_config, get_config_int
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Global cache for failure tracking
_failure_cache: dict[str, dict[str, Any]] = {}
_FAILURE_CACHE_MAX_KEYS = 50_000
_FAILURE_CACHE_CLEANUP_INTERVAL_SECONDS = 60
_failure_cache_state = {"last_cleanup_at": 0.0}

MAX_FAILURE_KEYS: dict[str, str] = {
    "admin_auth": "admin_auth_max_failures",
    "user_auth": "auth_password_max_failures",
}

LOCKOUT_DURATION_KEYS: dict[str, tuple[str, int]] = {
    "admin_auth": ("admin_auth_lockout_duration_minutes", 60),
    "user_auth": ("auth_password_lockout_duration_seconds", 1),
}

ADMIN_CAPTCHA_THRESHOLD_KEY = "admin_captcha_threshold_failures"

# Failure counting window (separate from lockout duration for clearer semantics).
FAILURE_WINDOW_KEYS: dict[str, tuple[str, int] | None] = {
    # Admin: reuse lockout duration as the failure counting window (no separate config yet).
    "admin_auth": None,
    "user_auth": ("auth_password_failure_window_seconds", 1),
}

AUTH_WHITELIST_KEYS: dict[str, str | None] = {
    "admin_auth": "admin_auth_whitelist",
    "user_auth": None,
}


def _maybe_cleanup_failure_cache(now: float) -> None:
    """Run periodic cleanup on auth hot paths."""
    if now - _failure_cache_state["last_cleanup_at"] < _FAILURE_CACHE_CLEANUP_INTERVAL_SECONDS:
        return
    cleanup_auth_tracker_cache(now=now)
    _failure_cache_state["last_cleanup_at"] = now


def _pick_failure_cache_eviction_key(now: float) -> str | None:
    """Pick the oldest non-protected key for eviction when capacity is reached."""
    selected_key: str | None = None
    selected_ts: float | None = None

    for key, data in _failure_cache.items():
        locked_until_raw = data.get("locked_until")
        locked_until = (
            float(locked_until_raw) if isinstance(locked_until_raw, int | float) else None
        )
        if locked_until is not None and locked_until > now:
            continue

        failures_raw = data.get("failures")
        failures = failures_raw if isinstance(failures_raw, deque) else None
        key_ts = failures[-1] if failures else 0.0
        if selected_ts is None or key_ts < selected_ts:
            selected_key = key
            selected_ts = key_ts

    return selected_key


def _ensure_failure_cache_capacity(now: float) -> None:
    """Bound failure cache size to avoid unbounded memory growth."""
    if len(_failure_cache) < _FAILURE_CACHE_MAX_KEYS:
        return

    cleanup_auth_tracker_cache(now=now)
    if len(_failure_cache) < _FAILURE_CACHE_MAX_KEYS:
        return

    evicted_key = _pick_failure_cache_eviction_key(now)
    if evicted_key is None:
        evicted_key = next(iter(_failure_cache))
    del _failure_cache[evicted_key]
    logger.warning(
        "auth_failure_cache_capacity_evicted",
        evicted_key=evicted_key,
        max_keys=_FAILURE_CACHE_MAX_KEYS,
        remaining_keys_count=len(_failure_cache),
    )


async def record_auth_failure(
    identifier: str,
    auth_type: str,
    db: AsyncSession,  # IP or user_id  # 'admin_auth' or 'user_auth'
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
    _maybe_cleanup_failure_cache(now)

    # Initialize cache for this key if not exists
    if cache_key not in _failure_cache:
        _ensure_failure_cache_capacity(now)
        _failure_cache[cache_key] = {"failures": deque(), "locked_until": None}

    # Record failure
    _failure_cache[cache_key]["failures"].append(now)

    if auth_type not in MAX_FAILURE_KEYS or auth_type not in LOCKOUT_DURATION_KEYS:
        raise ValueError(f"Unsupported auth_type: {auth_type}")

    max_failures = await get_config_int(db, key=MAX_FAILURE_KEYS[auth_type])
    duration_key, multiplier = LOCKOUT_DURATION_KEYS[auth_type]
    lockout_duration_value = await get_config_int(db, key=duration_key)
    lockout_duration = lockout_duration_value * multiplier

    # Clean old failures (outside failure counting window)
    failure_window_cfg = FAILURE_WINDOW_KEYS.get(auth_type)
    if failure_window_cfg is None:
        # Fallback: use lockout duration as the failure counting window.
        failure_window = lockout_duration
    else:
        failure_window_key, failure_window_multiplier = failure_window_cfg
        failure_window_value = await get_config_int(db, key=failure_window_key)
        failure_window = failure_window_value * failure_window_multiplier

    while _failure_cache[cache_key]["failures"] and _failure_cache[cache_key]["failures"][0] < (
        now - failure_window
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


async def check_lockout(
    identifier: str, auth_type: str, db: AsyncSession
) -> tuple[bool, int | None]:
    """
    Check if identifier is locked out.

    Args:
        identifier: IP address or user ID
        auth_type: Authentication type
        db: Database session

    Returns:
        (is_locked, remaining_seconds)
    """
    if auth_type not in AUTH_WHITELIST_KEYS:
        raise ValueError(f"Unsupported auth_type: {auth_type}")

    whitelist_key = AUTH_WHITELIST_KEYS.get(auth_type)
    if whitelist_key:
        whitelist_str = ""
        whitelist_value = await get_config(db, key=whitelist_key, required=False)
        if isinstance(whitelist_value, str):
            whitelist_str = whitelist_value.strip()
        elif whitelist_value is not None:
            whitelist_str = str(whitelist_value).strip()

        if whitelist_str:
            whitelist = [ip.strip() for ip in whitelist_str.split(",")]
            if identifier in whitelist:
                logger.debug("auth_whitelist_allowed", identifier=identifier, auth_type=auth_type)
                return False, None

    cache_key = f"{auth_type}:{identifier}"
    now = time.time()
    _maybe_cleanup_failure_cache(now)

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
    if auth_type != "admin_auth":
        raise ValueError(f"Unsupported auth_type: {auth_type}")

    captcha_provider_value = await get_config(db, key="admin_captcha_provider", required=False)
    if isinstance(captcha_provider_value, str):
        captcha_provider = captcha_provider_value.strip()
    elif captcha_provider_value is not None:
        captcha_provider = str(captcha_provider_value).strip()
    else:
        captcha_provider = ""

    if not captcha_provider or captcha_provider == "none":
        return False

    threshold = await get_config_int(db, key=ADMIN_CAPTCHA_THRESHOLD_KEY)

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


def cleanup_auth_tracker_cache(*, now: float | None = None) -> None:
    """
    Clean up auth tracker cache.

    Removes entries with no recent failures.
    Should be called periodically.
    """
    now_ts = time.time() if now is None else now
    keys_to_remove = []

    for key, data in _failure_cache.items():
        failures = data["failures"]

        # Clean old failures (older than 1 hour)
        while failures and failures[0] < now_ts - 3600:
            failures.popleft()

        # Mark key for removal if no recent failures and not locked
        if not failures and (not data["locked_until"] or data["locked_until"] <= now_ts):
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
