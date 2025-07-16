"""
LeanCloud Conversation Auto Setup
"""

import asyncio
import requests
from typing import Optional
from ...core.config import settings
from ...utils.logging import get_logger

logger = get_logger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds


async def ensure_unified_conversation() -> str:
    """
    Ensure unified conversation exists, create if not found.

    Returns:
        str: The conversation ID

    Raises:
        RuntimeError: If conversation cannot be created
    """
    from ..config_manager import (
        is_conversation_configured,
        get_unified_conversation_id,
        set_unified_conversation_id,
    )

    # Check if already configured
    if is_conversation_configured():
        conversation_id = get_unified_conversation_id()
        logger.info("unified_conversation_found", conversation_id=conversation_id)
        return conversation_id

    # Log LeanCloud configuration status
    logger.info(
        "leancloud_config_check",
        app_id=bool(settings.LEANCLOUD_APP_ID),
        master_key=bool(settings.LEANCLOUD_MASTER_KEY),
        base_url=settings.LEANCLOUD_BASE_URL,
    )

    # Auto-create
    logger.info("unified_conversation_not_found_creating")
    conversation_id = await create_system_conversation()

    if conversation_id:
        set_unified_conversation_id(conversation_id)
        logger.info("unified_conversation_created_and_saved", conversation_id=conversation_id)
        return conversation_id
    else:
        raise RuntimeError("Failed to create unified system conversation")


async def create_system_conversation() -> Optional[str]:
    """Create system conversation with retry mechanism."""
    for attempt in range(MAX_RETRIES):
        try:
            if attempt > 0:
                logger.info("retrying_conversation_creation", attempt=attempt + 1)
                await asyncio.sleep(RETRY_DELAY)

            conversation_id = await create_with_rest_api()
            if conversation_id:
                logger.info(
                    "conversation_created_successfully",
                    conversation_id=conversation_id,
                    attempt=attempt + 1,
                )
                return conversation_id

        except Exception as e:
            logger.error(
                "conversation_creation_attempt_failed", attempt=attempt + 1, error=str(e), exc_info=True
            )

            if attempt == MAX_RETRIES - 1:
                raise RuntimeError(
                    f"Failed to create unified conversation after {MAX_RETRIES} attempts. "
                    f"Please check LeanCloud credentials and network connectivity. "
                    f"Last error: {str(e)}"
                )

    return None


async def create_with_rest_api() -> str:
    """Create system conversation using LeanCloud REST API."""
    url = f"{settings.LEANCLOUD_BASE_URL}/1.2/rtm/service-conversations"

    headers = {
        "X-LC-Id": settings.LEANCLOUD_APP_ID,
        "X-LC-Key": f"{settings.LEANCLOUD_MASTER_KEY},master",
        "Content-Type": "application/json",
    }

    data = {
        "name": "message_service",
        "sys": True,
        "attr": {
            "created_by": "says",
            "auto_generated": True,
            "version": "1.0",
        },
    }

    logger.debug("creating_system_conversation", url=url, data=data)

    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, lambda: requests.post(url, headers=headers, json=data, timeout=30)
        )

        if response.status_code == 201:
            conversation = response.json()
            conversation_id = conversation["objectId"]
            logger.info(
                "system_conversation_created",
                conversation_id=conversation_id,
                name=conversation.get("name"),
            )
            return conversation_id
        else:
            error_msg = (
                f"LeanCloud API returned error. "
                f"Status: {response.status_code}, "
                f"Response: {response.text}"
            )
            logger.error("leancloud_api_error", status=response.status_code, response=response.text)
            raise RuntimeError(error_msg)

    except requests.RequestException as e:
        logger.error("network_error_creating_conversation", error=str(e))
        raise RuntimeError(f"Network error creating conversation: {str(e)}")
    except Exception as e:
        logger.error("unexpected_error_creating_conversation", error=str(e), exc_info=True)
        raise RuntimeError(f"Unexpected error creating conversation: {str(e)}")
