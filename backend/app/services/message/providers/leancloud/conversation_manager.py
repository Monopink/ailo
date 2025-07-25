"""
LeanCloud Conversation Manager

Functional module for managing LeanCloud conversation IDs using standard CRUD operations.
Integrates with system_config_crud for database persistence.
"""

import json
import requests
from sqlalchemy.ext.asyncio import AsyncSession

from crud.system_config import system_config_crud
from core.config import settings
from utils.logging import get_logger

logger = get_logger(__name__)

# Configuration key for storing LeanCloud conversation ID
LEANCLOUD_CONVERSATION_ID_KEY = "leancloud_conversation_id"
LEANCLOUD_CONVERSATION_ID_DESCRIPTION = "LeanCloud system conversation ID for message service"


async def get_leancloud_conversation_id(db: AsyncSession) -> str:
    """
    Get LeanCloud conversation ID from database.

    Args:
        db: Database session

    Returns:
        str: The conversation ID

    Raises:
        ValueError: If conversation ID is not configured
    """
    config_value = await system_config_crud.get_config_value(db, LEANCLOUD_CONVERSATION_ID_KEY)
    if not config_value:
        raise ValueError("LeanCloud conversation ID not configured")

    logger.debug("leancloud_conversation_id_retrieved", conversation_id=config_value)
    return config_value


async def create_and_save_leancloud_conversation_id(db: AsyncSession) -> str:
    """
    Create new LeanCloud conversation ID and save to database.

    Args:
        db: Database session

    Returns:
        str: The newly created conversation ID

    Raises:
        RuntimeError: If LeanCloud API fails
    """
    conversation_id = await _create_leancloud_conversation_via_api()

    await system_config_crud.set_config(
        db, LEANCLOUD_CONVERSATION_ID_KEY, conversation_id, LEANCLOUD_CONVERSATION_ID_DESCRIPTION
    )

    logger.info("leancloud_conversation_id_created_and_saved", conversation_id=conversation_id)
    return conversation_id


async def validate_leancloud_conversation_exists(conversation_id: str) -> bool:
    """
    Validate if LeanCloud conversation exists on LeanCloud server.

    Args:
        conversation_id: The conversation ID to validate

    Returns:
        bool: True if conversation exists, False otherwise
    """
    try:
        url = f"{settings.LEANCLOUD_BASE_URL}/1.2/rtm/service-conversations"
        headers = {
            "X-LC-Id": settings.LEANCLOUD_APP_ID,
            "X-LC-Key": f"{settings.LEANCLOUD_MASTER_KEY},master",
        }
        params = {"where": json.dumps({"objectId": conversation_id})}

        response = requests.get(url, headers=headers, params=params, timeout=10)

        if response.status_code == 200:
            data = response.json()
            exists = len(data.get("results", [])) > 0
            logger.debug(
                "leancloud_conversation_validation_result", conversation_id=conversation_id, exists=exists
            )
            return exists
        else:
            logger.warning(
                "leancloud_conversation_validation_failed",
                conversation_id=conversation_id,
                status_code=response.status_code,
            )
            return False

    except Exception as e:
        logger.error("validate_leancloud_conversation_error", conversation_id=conversation_id, error=str(e))
        return False


async def _create_leancloud_conversation_via_api() -> str:
    """
    Create LeanCloud service conversation via REST API.

    Returns:
        str: The created conversation ID (objectId)

    Raises:
        RuntimeError: If API call fails
    """
    url = f"{settings.LEANCLOUD_BASE_URL}/1.2/rtm/service-conversations"

    headers = {
        "X-LC-Id": settings.LEANCLOUD_APP_ID,
        "X-LC-Key": f"{settings.LEANCLOUD_MASTER_KEY},master",
        "Content-Type": "application/json",
    }

    data = {
        "name": "leancloud_message_service",
        "sys": True,
        "attr": {
            "created_by": "says",
            "auto_generated": True,
            "version": "1.0",
        },
    }

    logger.debug("creating_leancloud_conversation", url=url, data=data)

    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)

        if response.status_code == 201:
            conversation = response.json()
            conversation_id = conversation["objectId"]
            logger.info(
                "leancloud_conversation_created",
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
        logger.error("network_error_creating_leancloud_conversation", error=str(e))
        raise RuntimeError(f"Network error creating LeanCloud conversation: {str(e)}")
    except Exception as e:
        logger.error("unexpected_error_creating_leancloud_conversation", error=str(e))
        raise RuntimeError(f"Unexpected error creating LeanCloud conversation: {str(e)}")
