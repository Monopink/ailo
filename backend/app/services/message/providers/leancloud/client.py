"""
LeanCloud REST API client functions.

This module provides pure functions for LeanCloud REST API calls.
All functions are stateless and return explicit results.
"""

from typing import Any

import httpx
from utils.logging import get_logger

logger = get_logger(__name__)


async def create_system_conversation(
    app_id: str, master_key: str, base_url: str, name: str = "uni_conversation_id"
) -> tuple[bool, str | None, str | None]:
    """
    Create LeanCloud system conversation (service conversation).

    Pure function that calls LeanCloud REST API to create a system conversation.

    Args:
        app_id: LeanCloud App ID
        master_key: LeanCloud Master Key
        base_url: LeanCloud base URL
        name: System conversation name

    Returns:
        Tuple of (success, conversation_id, error_message)
        - success: True if creation successful
        - conversation_id: LeanCloud conversation ID (objectId) if successful
        - error_message: Error message if failed

    Example:
        success, conv_id, error = await create_system_conversation(
            app_id="xxx",
            master_key="yyy",
            base_url="https://example.com",
            name="uni_conversation_id"
        )
    """
    url = f"{base_url}/1.2/rtm/service-conversations"
    headers = {
        "X-LC-Id": app_id,
        "X-LC-Key": f"{master_key},master",
        "Content-Type": "application/json",
    }
    body = {"name": name}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, headers=headers, json=body)

            if response.status_code == 201 or response.status_code == 200:
                data = response.json()
                conversation_id = data.get("objectId")
                if conversation_id:
                    logger.info(
                        "leancloud_system_conversation_created",
                        conversation_id=conversation_id,
                        name=name,
                    )
                    return True, conversation_id, None
                error_msg = "Response missing objectId field"
                logger.error("leancloud_create_conversation_invalid_response", response=data)
                return False, None, error_msg
            error_msg = f"HTTP {response.status_code}: {response.text}"
            logger.error(
                "leancloud_create_conversation_failed",
                status_code=response.status_code,
                response=response.text,
            )
            return False, None, error_msg

    except httpx.TimeoutException as e:
        error_msg = f"Request timeout: {e!s}"
        logger.error("leancloud_create_conversation_timeout", error=str(e))
        return False, None, error_msg
    except httpx.HTTPError as e:
        error_msg = f"HTTP error: {e!s}"
        logger.error("leancloud_create_conversation_http_error", error=str(e))
        return False, None, error_msg
    except Exception as e:
        error_msg = f"Unexpected error: {e!s}"
        logger.error("leancloud_create_conversation_unexpected_error", error=str(e))
        return False, None, error_msg


async def check_service_conversation_exists(
    app_id: str, master_key: str, base_url: str, conversation_id: str
) -> tuple[bool, str | None]:
    """
    Check if a LeanCloud service conversation exists.

    Args:
        app_id: LeanCloud App ID
        master_key: LeanCloud Master Key
        base_url: LeanCloud base URL
        conversation_id: Conversation ID to check

    Returns:
        Tuple of (exists, error_message)
        - exists: True if the conversation exists
        - error_message: Optional descriptive error for non-404 failures
    """
    url = f"{base_url}/1.2/rtm/service-conversations/{conversation_id}"
    headers = {"X-LC-Id": app_id, "X-LC-Key": f"{master_key},master"}

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url, headers=headers)

        if response.status_code == 200:
            logger.debug(
                "leancloud_conversation_exists",
                conversation_id=conversation_id,
            )
            return True, None

        if response.status_code == 404:
            logger.warning(
                "leancloud_conversation_missing",
                conversation_id=conversation_id,
            )
            return False, None

        error_msg = f"HTTP {response.status_code}: {response.text}"
        logger.error(
            "leancloud_check_conversation_failed",
            conversation_id=conversation_id,
            response=response.text,
            status_code=response.status_code,
        )
        return False, error_msg

    except httpx.TimeoutException as error:
        logger.error("leancloud_check_conversation_timeout", error=str(error))
        return False, f"Request timeout: {error}"
    except httpx.HTTPError as error:
        logger.error("leancloud_check_conversation_http_error", error=str(error))
        return False, f"HTTP error: {error}"
    except Exception as error:
        logger.error("leancloud_check_conversation_unexpected", error=str(error))
        return False, f"Unexpected error: {error}"


async def subscribe_user_to_conversation(
    app_id: str, master_key: str, base_url: str, conversation_id: str, client_id: str
) -> tuple[bool, str | None]:
    """
    Subscribe user to LeanCloud system conversation.

    Args:
        app_id: LeanCloud App ID
        master_key: LeanCloud Master Key
        base_url: LeanCloud base URL
        conversation_id: System conversation ID
        client_id: User's client ID (qiao_id)

    Returns:
        Tuple of (success, error_message)
    """
    url = f"{base_url}/1.2/rtm/service-conversations/{conversation_id}/subscribers"
    headers = {
        "X-LC-Id": app_id,
        "X-LC-Key": f"{master_key},master",
        "Content-Type": "application/json",
    }
    body = {"client_id": client_id}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, headers=headers, json=body)

            if response.status_code == 200:
                logger.info(
                    "leancloud_user_subscribed",
                    conversation_id=conversation_id,
                    client_id=client_id,
                )
                return True, None
            error_msg = f"HTTP {response.status_code}: {response.text}"
            logger.error(
                "leancloud_subscribe_failed",
                conversation_id=conversation_id,
                client_id=client_id,
                status_code=response.status_code,
                response=response.text,
            )
            return False, error_msg

    except httpx.TimeoutException as e:
        error_msg = f"Request timeout: {e!s}"
        logger.error("leancloud_subscribe_timeout", error=str(e))
        return False, error_msg
    except httpx.HTTPError as e:
        error_msg = f"HTTP error: {e!s}"
        logger.error("leancloud_subscribe_http_error", error=str(e))
        return False, error_msg
    except Exception as e:
        error_msg = f"Unexpected error: {e!s}"
        logger.error("leancloud_subscribe_unexpected_error", error=str(e))
        return False, error_msg


async def unsubscribe_user_from_conversation(
    app_id: str, master_key: str, base_url: str, conversation_id: str, client_id: str
) -> tuple[bool, str | None]:
    """
    Unsubscribe user from LeanCloud system conversation.

    Args:
        app_id: LeanCloud App ID
        master_key: LeanCloud Master Key
        base_url: LeanCloud base URL
        conversation_id: System conversation ID
        client_id: User's client ID (qiao_id)

    Returns:
        Tuple of (success, error_message)
    """
    url = f"{base_url}/1.2/rtm/service-conversations/{conversation_id}/subscribers/{client_id}"
    headers = {"X-LC-Id": app_id, "X-LC-Key": f"{master_key},master"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.delete(url, headers=headers)

            if response.status_code == 200:
                logger.info(
                    "leancloud_user_unsubscribed",
                    conversation_id=conversation_id,
                    client_id=client_id,
                )
                return True, None
            error_msg = f"HTTP {response.status_code}: {response.text}"
            logger.error(
                "leancloud_unsubscribe_failed",
                conversation_id=conversation_id,
                client_id=client_id,
                status_code=response.status_code,
                response=response.text,
            )
            return False, error_msg

    except httpx.TimeoutException as e:
        error_msg = f"Request timeout: {e!s}"
        logger.error("leancloud_unsubscribe_timeout", error=str(e))
        return False, error_msg
    except httpx.HTTPError as e:
        error_msg = f"HTTP error: {e!s}"
        logger.error("leancloud_unsubscribe_http_error", error=str(e))
        return False, error_msg
    except Exception as e:
        error_msg = f"Unexpected error: {e!s}"
        logger.error("leancloud_unsubscribe_unexpected_error", error=str(e))
        return False, error_msg


async def send_service_message(
    app_id: str,
    master_key: str,
    base_url: str,
    conversation_id: str,
    from_client: str,
    to_clients: list[str],
    message: str,
) -> tuple[bool, str | None, str | None]:
    """
    Send message through LeanCloud service conversation.

    Args:
        app_id: LeanCloud App ID
        master_key: LeanCloud Master Key
        base_url: LeanCloud base URL
        conversation_id: Service conversation ID
        from_client: Sender's client ID (qiao_id)
        to_clients: List of recipient client IDs (qiao_ids)
        message: Message content (string)

    Returns:
        Tuple of (success, msg_id, error_message)
        - success: True if send successful
        - msg_id: LeanCloud message ID if successful
        - error_message: Error message if failed
    """
    url = f"{base_url}/1.2/rtm/service-conversations/{conversation_id}/messages"
    headers = {
        "X-LC-Id": app_id,
        "X-LC-Key": f"{master_key},master",
        "Content-Type": "application/json",
    }
    body = {"from_client": from_client, "to_clients": to_clients, "message": message}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, headers=headers, json=body)

            if response.status_code == 200:
                data = response.json()
                msg_id = _extract_msg_id(data)
                if msg_id:
                    logger.info(
                        "leancloud_message_sent",
                        conversation_id=conversation_id,
                        from_client=from_client,
                        to_clients=to_clients,
                        msg_id=msg_id,
                    )
                    return True, msg_id, None
                error_msg = "Response missing msg-id field"
                logger.error("leancloud_send_message_invalid_response", response=data)
                return False, None, error_msg
            error_msg = f"HTTP {response.status_code}: {response.text}"
            logger.error(
                "leancloud_send_message_failed",
                conversation_id=conversation_id,
                status_code=response.status_code,
                response=response.text,
            )
            return False, None, error_msg

    except httpx.TimeoutException as e:
        error_msg = f"Request timeout: {e!s}"
        logger.error("leancloud_send_message_timeout", error=str(e))
        return False, None, error_msg
    except httpx.HTTPError as e:
        error_msg = f"HTTP error: {e!s}"
        logger.error("leancloud_send_message_http_error", error=str(e))
        return False, None, error_msg
    except Exception as e:
        error_msg = f"Unexpected error: {e!s}"
        logger.error("leancloud_send_message_unexpected_error", error=str(e))
        return False, None, error_msg


def _extract_msg_id(response_data: dict[str, Any]) -> str | None:
    """
    LeanCloud responses sometimes wrap msg-id inside a result envelope.
    This helper normalizes the lookup so provider callers always get the ID.
    """
    if not isinstance(response_data, dict):
        return None

    candidates = [
        response_data.get("msg-id"),
        response_data.get("msgId"),
    ]

    result_section = response_data.get("result")
    if isinstance(result_section, dict):
        candidates.extend(
            [
                result_section.get("msg-id"),
                result_section.get("msgId"),
            ]
        )

    for value in candidates:
        if isinstance(value, str) and value:
            return value
    return None
