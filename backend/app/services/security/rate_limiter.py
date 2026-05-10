"""
Business Rate Limiter

Provides rate limiting for business operations (auth, SMS, message).
Uses database configuration and supports whitelist.
"""

import time
from collections import deque

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.system_config import get_config, get_config_int
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Global cache for rate limiting
_rate_limit_cache: dict[str, deque[float]] = {}
_RATE_LIMIT_CACHE_MAX_KEYS = 50_000
_RATE_LIMIT_CACHE_CLEANUP_INTERVAL_SECONDS = 60
_rate_limit_cache_state = {"last_cleanup_at": 0.0}

RATE_LIMIT_REQUEST_KEYS: dict[str, str] = {
    "admin_auth": "admin_auth_rate_limit_requests",
    "auth_password_short": "auth_password_rate_limit_short_requests",
    "auth_password_long": "auth_password_rate_limit_long_requests",
    "sms": "sms_rate_limit_requests",
    "message_short": "message_rate_limit_short_requests",
    "message_long": "message_rate_limit_long_requests",
    "username_check_short": "username_check_rate_limit_short_requests",
    "username_check_long": "username_check_rate_limit_long_requests",
    "username_submit": "username_submit_rate_limit_requests",
    "square": "square_rate_limit_requests",
    "square_refresh": "square_refresh_rate_limit_requests",
    "square_load_more": "square_load_more_rate_limit_requests",
    "media_upload": "media_upload_rate_limit_requests",
    "invite_code_resolve": "invite_code_resolve_rate_limit_requests",
    "invite_code_bind": "invite_code_bind_rate_limit_requests",
    "runtime_observation": "runtime_observation_rate_limit_requests",
    "runtime_preflight_probe": "runtime_preflight_probe_rate_limit_requests",
    "public_invite_intake": "public_invite_intake_rate_limit_requests",
    "sms_verify": "sms_verify_rate_limit_requests",
}

RATE_LIMIT_WINDOW_KEYS: dict[str, tuple[str, int]] = {
    "admin_auth": ("admin_auth_rate_limit_window_seconds", 1),
    "auth_password_short": ("auth_password_rate_limit_short_window_seconds", 1),
    "auth_password_long": ("auth_password_rate_limit_long_window_seconds", 1),
    "sms": ("sms_rate_limit_window_seconds", 1),
    "message_short": ("message_rate_limit_short_window_seconds", 1),
    "message_long": ("message_rate_limit_long_window_seconds", 1),
    "username_check_short": ("username_check_rate_limit_short_window_seconds", 1),
    "username_check_long": ("username_check_rate_limit_long_window_seconds", 1),
    "username_submit": ("username_submit_rate_limit_window_seconds", 1),
    "square": ("square_rate_limit_window_seconds", 1),
    "square_refresh": ("square_refresh_rate_limit_window_seconds", 1),
    "square_load_more": ("square_load_more_rate_limit_window_seconds", 1),
    "media_upload": ("media_upload_rate_limit_window_seconds", 1),
    "invite_code_resolve": ("invite_code_resolve_rate_limit_window_seconds", 1),
    "invite_code_bind": ("invite_code_bind_rate_limit_window_seconds", 1),
    "runtime_observation": ("runtime_observation_rate_limit_window_seconds", 1),
    "runtime_preflight_probe": ("runtime_preflight_probe_rate_limit_window_seconds", 1),
    "public_invite_intake": ("public_invite_intake_rate_limit_window_seconds", 1),
    "sms_verify": ("sms_verify_rate_limit_window_seconds", 1),
}

RATE_LIMIT_WHITELIST_KEYS: dict[str, str | None] = {
    "admin_auth": "admin_auth_whitelist",
    "auth_password_short": None,
    "auth_password_long": None,
    "sms": "sms_whitelist",
    "message_short": None,
    "message_long": None,
    "username_check_short": None,
    "username_check_long": None,
    "username_submit": None,
    "square": None,
    "square_refresh": None,
    "square_load_more": None,
    "media_upload": None,
    "invite_code_resolve": None,
    "invite_code_bind": None,
    "runtime_observation": None,
    "runtime_preflight_probe": None,
    "public_invite_intake": None,
    "sms_verify": None,
}


async def _load_rate_limit_group_settings(
    group: str,
    db: AsyncSession,
) -> tuple[int, float, set[str]]:
    if group not in RATE_LIMIT_REQUEST_KEYS or group not in RATE_LIMIT_WINDOW_KEYS:
        raise ValueError(f"Unsupported rate limit group: {group}")

    request_key = RATE_LIMIT_REQUEST_KEYS[group]
    window_key, multiplier = RATE_LIMIT_WINDOW_KEYS[group]
    requests = await get_config_int(db, key=request_key)
    base_window = await get_config_int(db, key=window_key)
    window = float(base_window * multiplier)

    whitelist_key = RATE_LIMIT_WHITELIST_KEYS.get(group)
    whitelist: set[str] = set()
    if whitelist_key:
        whitelist_value = await get_config(db, key=whitelist_key, required=False)
        if isinstance(whitelist_value, str):
            whitelist_str = whitelist_value.strip()
        elif whitelist_value is None:
            whitelist_str = ""
        else:
            whitelist_str = str(whitelist_value).strip()
        if whitelist_str:
            whitelist = {item.strip() for item in whitelist_str.split(",") if item.strip() != ""}
    return requests, window, whitelist


def _check_single_cache_key_limit(
    *,
    cache_key: str,
    now: float,
    window: float,
    requests: int,
) -> tuple[bool, int | None, int]:
    if cache_key not in _rate_limit_cache:
        _ensure_rate_limit_cache_capacity(now)
        _rate_limit_cache[cache_key] = deque()

    while _rate_limit_cache[cache_key] and _rate_limit_cache[cache_key][0] < now - window:
        _rate_limit_cache[cache_key].popleft()

    current_count = len(_rate_limit_cache[cache_key])
    if current_count >= requests:
        oldest_request = _rate_limit_cache[cache_key][0]
        retry_after = int(window - (now - oldest_request)) + 1
        return False, retry_after, current_count

    return True, None, current_count


def _record_cache_key_hit(cache_key: str, *, now: float) -> int:
    _rate_limit_cache[cache_key].append(now)
    return len(_rate_limit_cache[cache_key])


def _maybe_cleanup_rate_limit_cache(now: float) -> None:
    """Run periodic cleanup on the hot path without a background scheduler."""
    if (
        now - _rate_limit_cache_state["last_cleanup_at"]
        < _RATE_LIMIT_CACHE_CLEANUP_INTERVAL_SECONDS
    ):
        return
    cleanup_rate_limit_cache(now=now)
    _rate_limit_cache_state["last_cleanup_at"] = now


def _ensure_rate_limit_cache_capacity(now: float) -> None:
    """Bound cache size to avoid unbounded memory growth."""
    if len(_rate_limit_cache) < _RATE_LIMIT_CACHE_MAX_KEYS:
        return

    cleanup_rate_limit_cache(now=now)
    if len(_rate_limit_cache) < _RATE_LIMIT_CACHE_MAX_KEYS:
        return

    evicted_key = next(iter(_rate_limit_cache))
    del _rate_limit_cache[evicted_key]
    logger.warning(
        "rate_limit_cache_capacity_evicted",
        evicted_key=evicted_key,
        max_keys=_RATE_LIMIT_CACHE_MAX_KEYS,
        remaining_keys_count=len(_rate_limit_cache),
    )


async def check_rate_limit(
    identifier: str,  # IP or user_id
    group: str,  # e.g. 'admin_auth', 'auth_password_short', 'message_short'
    db: AsyncSession,
) -> tuple[bool, str | None, int | None]:
    """
    Check rate limit for a specific group.

    Args:
        identifier: IP address or user ID
        group: Rate limit group name
        db: Database session

    Returns:
        (is_allowed, error_code, retry_after_seconds)
    """
    requests, window, whitelist = await _load_rate_limit_group_settings(group, db)

    if identifier in whitelist:
        logger.debug("rate_limit_whitelist_allowed", identifier=identifier, group=group)
        return True, None, None

    # Check rate limit
    cache_key = f"{group}:{identifier}"
    now = time.time()
    _maybe_cleanup_rate_limit_cache(now)
    allowed, retry_after, current_count = _check_single_cache_key_limit(
        cache_key=cache_key,
        now=now,
        window=window,
        requests=requests,
    )
    if not allowed:
        logger.warning(
            "rate_limit_exceeded",
            identifier=identifier,
            group=group,
            requests_count=current_count,
            retry_after=retry_after,
        )

        error_code = f"RATE_LIMIT_EXCEEDED_{group.upper()}"
        return False, error_code, retry_after

    requests_count = _record_cache_key_hit(cache_key, now=now)

    logger.debug(
        "rate_limit_allowed",
        identifier=identifier,
        group=group,
        requests_count=requests_count,
        limit=requests,
    )

    return True, None, None


async def check_rate_limits_atomic(
    identifiers: tuple[str, ...],
    group: str,
    db: AsyncSession,
) -> tuple[bool, str | None, int | None]:
    """Check multiple identifiers atomically and only record if all pass."""
    normalized_identifiers = tuple(
        dict.fromkeys(identifier for identifier in identifiers if identifier)
    )
    if len(normalized_identifiers) == 0:
        return True, None, None

    requests, window, whitelist = await _load_rate_limit_group_settings(group, db)
    now = time.time()
    _maybe_cleanup_rate_limit_cache(now)

    pending_cache_keys: list[tuple[str, str]] = []
    for identifier in normalized_identifiers:
        if identifier in whitelist:
            logger.debug("rate_limit_whitelist_allowed", identifier=identifier, group=group)
            continue

        cache_key = f"{group}:{identifier}"
        allowed, retry_after, current_count = _check_single_cache_key_limit(
            cache_key=cache_key,
            now=now,
            window=window,
            requests=requests,
        )
        if not allowed:
            logger.warning(
                "rate_limit_exceeded",
                identifier=identifier,
                group=group,
                requests_count=current_count,
                retry_after=retry_after,
            )
            error_code = f"RATE_LIMIT_EXCEEDED_{group.upper()}"
            return False, error_code, retry_after
        pending_cache_keys.append((identifier, cache_key))

    for identifier, cache_key in pending_cache_keys:
        requests_count = _record_cache_key_hit(cache_key, now=now)
        logger.debug(
            "rate_limit_allowed",
            identifier=identifier,
            group=group,
            requests_count=requests_count,
            limit=requests,
        )

    return True, None, None


async def check_message_rate_limit(
    identifier: str, db: AsyncSession
) -> tuple[bool, str | None, int | None]:
    """
    Check message rate limit with dual constraints.

    Messages have two independent rate limits:
    - Short-term: 5 messages / 10 seconds
    - Long-term: 20 messages / 60 seconds

    Args:
        identifier: User ID
        db: Database session

    Returns:
        (is_allowed, error_code, retry_after_seconds)
    """
    # Check short-term limit (5 messages / 10 seconds)
    allowed, _error, retry = await check_rate_limit(identifier, "message_short", db)
    if not allowed:
        return False, "MESSAGE_RATE_LIMIT_SHORT", retry

    # Check long-term limit (20 messages / 60 seconds)
    allowed, _error, retry = await check_rate_limit(identifier, "message_long", db)
    if not allowed:
        return False, "MESSAGE_RATE_LIMIT_LONG", retry

    return True, None, None


async def check_password_login_rate_limit(
    identifier: str, db: AsyncSession
) -> tuple[bool, str | None, int | None]:
    """
    Check password login rate limit with dual constraints.

    This is intentionally separated from generic "user_auth" limits because
    password login is the highest-risk auth path (credential stuffing).

    Args:
        identifier: "{client_ip}:{identifier_key}"
        db: Database session

    Returns:
        (is_allowed, error_code, retry_after_seconds)
    """
    allowed, _error, retry = await check_rate_limit(identifier, "auth_password_short", db)
    if not allowed:
        return False, "PASSWORD_LOGIN_RATE_LIMIT_SHORT", retry

    allowed, _error, retry = await check_rate_limit(identifier, "auth_password_long", db)
    if not allowed:
        return False, "PASSWORD_LOGIN_RATE_LIMIT_LONG", retry

    return True, None, None


async def check_username_check_rate_limit(
    identifier: str, db: AsyncSession
) -> tuple[bool, str | None, int | None]:
    """Check username availability-check rate limit with dual constraints."""
    allowed, _error, retry = await check_rate_limit(identifier, "username_check_short", db)
    if not allowed:
        return False, "USERNAME_CHECK_RATE_LIMIT_SHORT", retry

    allowed, _error, retry = await check_rate_limit(identifier, "username_check_long", db)
    if not allowed:
        return False, "USERNAME_CHECK_RATE_LIMIT_LONG", retry

    return True, None, None


async def check_username_submit_rate_limit(
    identifier: str, db: AsyncSession
) -> tuple[bool, str | None, int | None]:
    """Check username submit rate limit for first-set attempts."""
    allowed, _error, retry = await check_rate_limit(identifier, "username_submit", db)
    if not allowed:
        return False, "USERNAME_SUBMIT_RATE_LIMIT", retry

    return True, None, None


def cleanup_rate_limit_cache(*, now: float | None = None) -> None:
    """
    Clean up rate limit cache.

    Removes entries with no recent requests.
    Should be called periodically.
    """
    now_ts = time.time() if now is None else now
    keys_to_remove = []

    for key, requests in _rate_limit_cache.items():
        # Assume max window is 3600 seconds (1 hour)
        while requests and requests[0] < now_ts - 3600:
            requests.popleft()

        # Mark key for removal if no recent requests
        if not requests:
            keys_to_remove.append(key)

    # Remove marked keys
    for key in keys_to_remove:
        del _rate_limit_cache[key]

    if keys_to_remove:
        logger.info(
            "rate_limit_cache_cleaned",
            removed_keys_count=len(keys_to_remove),
            remaining_keys_count=len(_rate_limit_cache),
        )
