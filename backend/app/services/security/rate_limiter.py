"""
Business Rate Limiter

Provides rate limiting for business operations (auth, SMS, message).
Uses database configuration and supports whitelist.
"""

from typing import Dict, Tuple, Optional
from collections import deque
from sqlalchemy.ext.asyncio import AsyncSession
import time

from services.system_config import get_config
from utils.logging import get_logger

logger = get_logger(__name__)

# Global cache for rate limiting
_rate_limit_cache: Dict[str, deque] = {}


async def check_rate_limit(
    identifier: str,  # IP or user_id
    group: str,       # 'admin_auth', 'user_auth', 'sms', 'message_short', 'message_long'
    db: AsyncSession
) -> Tuple[bool, Optional[str], Optional[int]]:
    """
    Check rate limit for a specific group.
    
    Args:
        identifier: IP address or user ID
        group: Rate limit group name
        db: Database session
        
    Returns:
        (is_allowed, error_code, retry_after_seconds)
    """
    # Get configuration
    requests = int(await get_config(
        db,
        key=f"{group}_rate_limit_requests",
        default=100
    ))
    window = int(await get_config(
        db,
        key=f"{group}_rate_limit_window",
        default=60
    ))
    
    # Check whitelist
    whitelist_str = await get_config(
        db,
        key=f"{group.split('_')[0]}_whitelist",  # Extract prefix (admin, user, sms, api)
        default=""
    )
    
    if whitelist_str:
        whitelist = [ip.strip() for ip in whitelist_str.split(',')]
        if identifier in whitelist:
            logger.debug(
                "rate_limit_whitelist_allowed",
                identifier=identifier,
                group=group
            )
            return True, None, None
    
    # Check rate limit
    cache_key = f"{group}:{identifier}"
    now = time.time()
    
    # Initialize cache for this key if not exists
    if cache_key not in _rate_limit_cache:
        _rate_limit_cache[cache_key] = deque()
    
    # Remove old requests outside the window
    while _rate_limit_cache[cache_key] and _rate_limit_cache[cache_key][0] < now - window:
        _rate_limit_cache[cache_key].popleft()
    
    # Check if limit exceeded
    if len(_rate_limit_cache[cache_key]) >= requests:
        # Calculate retry_after
        oldest_request = _rate_limit_cache[cache_key][0]
        retry_after = int(window - (now - oldest_request)) + 1
        
        logger.warning(
            "rate_limit_exceeded",
            identifier=identifier,
            group=group,
            requests_count=len(_rate_limit_cache[cache_key]),
            retry_after=retry_after
        )
        
        error_code = f"RATE_LIMIT_EXCEEDED_{group.upper()}"
        return False, error_code, retry_after
    
    # Record this request
    _rate_limit_cache[cache_key].append(now)
    
    logger.debug(
        "rate_limit_allowed",
        identifier=identifier,
        group=group,
        requests_count=len(_rate_limit_cache[cache_key]),
        limit=requests
    )
    
    return True, None, None


async def check_message_rate_limit(
    identifier: str,
    db: AsyncSession
) -> Tuple[bool, Optional[str], Optional[int]]:
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
    allowed, error, retry = await check_rate_limit(
        identifier, 'message_short', db
    )
    if not allowed:
        return False, "MESSAGE_RATE_LIMIT_SHORT", retry
    
    # Check long-term limit (20 messages / 60 seconds)
    allowed, error, retry = await check_rate_limit(
        identifier, 'message_long', db
    )
    if not allowed:
        return False, "MESSAGE_RATE_LIMIT_LONG", retry
    
    return True, None, None


def cleanup_rate_limit_cache() -> None:
    """
    Clean up rate limit cache.
    
    Removes entries with no recent requests.
    Should be called periodically.
    """
    global _rate_limit_cache
    
    now = time.time()
    keys_to_remove = []
    
    for key, requests in _rate_limit_cache.items():
        # Assume max window is 3600 seconds (1 hour)
        while requests and requests[0] < now - 3600:
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
            remaining_keys_count=len(_rate_limit_cache)
        )

