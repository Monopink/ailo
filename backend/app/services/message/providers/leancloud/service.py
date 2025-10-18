"""
LeanCloud Message Service Startup Check

Provides startup validation functions for LeanCloud message service.
Ensures API connectivity and conversation ID configuration before service starts.
"""

import requests
from typing import Optional

from core.config import settings
from core.database import SessionLocal
from utils.logging import get_logger
from .conversation_manager import get_leancloud_conversation_id

logger = get_logger(__name__)

# Module-level cache for conversation ID
_cached_conversation_id: Optional[str] = None


async def _get_cached_conversation_id() -> str:
    """
    Get conversation ID from cache or database.

    Returns:
        str: The conversation ID

    Raises:
        ValueError: If conversation ID is not configured
    """
    global _cached_conversation_id

    if _cached_conversation_id is None:
        async with SessionLocal() as db:
            _cached_conversation_id = await get_leancloud_conversation_id(db)
            logger.debug("leancloud_conversation_id_cached", conversation_id=_cached_conversation_id)

    return _cached_conversation_id


def _clear_conversation_id_cache() -> None:
    """Clear the cached conversation ID (for testing or reset purposes)."""
    global _cached_conversation_id
    _cached_conversation_id = None
    logger.debug("leancloud_conversation_id_cache_cleared")


async def startup_leancloud_message_service_check() -> bool:
    """
    Perform startup validation for LeanCloud message service.

    Returns:
        bool: True if all checks pass, False otherwise
    """
    try:
        logger.info("starting_leancloud_message_service_check")

        # Check LeanCloud API connectivity
        if not _check_leancloud_api_connectivity():
            logger.error("leancloud_api_connectivity_check_failed")
            return False

        # Ensure conversation ID is valid
        if not await _ensure_leancloud_conversation_id_valid():
            logger.error("leancloud_conversation_id_validation_failed")
            return False

        logger.info("leancloud_message_service_startup_check_passed")
        return True

    except Exception as e:
        logger.error("leancloud_message_service_startup_check_failed", error=str(e), exc_info=True)
        return False


def _check_leancloud_api_connectivity() -> bool:
    """
    Check LeanCloud API connectivity by making a test request.

    Returns:
        bool: True if API is accessible, False otherwise
    """
    try:
        # Validate required settings
        app_id = settings.LEANCLOUD_APP_ID
        master_key = settings.LEANCLOUD_MASTER_KEY
        base_url = settings.LEANCLOUD_BASE_URL

        if not app_id or not master_key or not base_url:
            logger.error("leancloud_credentials_missing")
            return False

        # Test API access by querying service conversations
        url = f"{base_url}/1.2/rtm/service-conversations"
        headers = {
            "X-LC-Id": app_id,
            "X-LC-Key": f"{master_key},master",
            "Content-Type": "application/json",
        }

        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code in [200, 404]:  # 404 is OK if no conversations exist
            logger.info("leancloud_api_connectivity_verified")
            return True
        else:
            logger.error("leancloud_api_connectivity_failed", status_code=response.status_code)
            return False

    except requests.RequestException as e:
        logger.error("leancloud_api_connectivity_error", error=str(e))
        return False
    except Exception as e:
        logger.error("leancloud_api_connectivity_unexpected_error", error=str(e), exc_info=True)
        return False


async def _ensure_leancloud_conversation_id_valid() -> bool:
    """
    Ensure LeanCloud conversation ID is configured and valid.
    Creates conversation ID if not exists.

    Returns:
        bool: True if conversation ID is valid, False otherwise
    """
    try:
        # Try to get conversation ID using cached function
        try:
            conversation_id = await _get_cached_conversation_id()
            logger.info("leancloud_conversation_id_found", conversation_id=conversation_id)
            return True
        except ValueError:
            # Conversation ID not configured, create one
            logger.info("leancloud_conversation_id_not_found_creating_new")

            # Import here to avoid circular imports
            from .conversation_manager import create_and_save_leancloud_conversation_id

            async with SessionLocal() as db:
                conversation_id = await create_and_save_leancloud_conversation_id(db)

            # Update cache with new conversation ID
            global _cached_conversation_id
            _cached_conversation_id = conversation_id

            logger.info("leancloud_conversation_id_created_and_cached", conversation_id=conversation_id)
            return True

    except Exception as e:
        logger.error("leancloud_conversation_id_unexpected_error", error=str(e), exc_info=True)
        return False


# Export the cached conversation ID getter for use by other modules
get_cached_conversation_id = _get_cached_conversation_id
clear_conversation_id_cache = _clear_conversation_id_cache
