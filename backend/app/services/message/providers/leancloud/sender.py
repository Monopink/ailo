"""
LeanCloud Message Sender

Handles outgoing message sending functionality for LeanCloud service.
Provides functions for sending regular messages and system messages.
"""

import json
import requests
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from core.config import settings
from enums import MessageType, IMServiceType
from core.event_bus import event_bus, EventTypes
from utils.logging import get_logger
from .startup import get_cached_conversation_id

logger = get_logger(__name__)


# Core LeanCloud API Functions


def create_structured_message(data: Dict[str, Any]) -> str:
    """
    Create structured message format for frontend consumption.
    This wraps the message data in the format expected by frontend.

    Args:
        data: Message data dictionary

    Returns:
        str: JSON string of structured message

    Raises:
        ValueError: If data is invalid or missing required fields
    """
    try:
        from_entity = data.get("from_entity")
        to_entity = data.get("to_entity")
        content = data.get("content", "")
        message_type = data.get("message_type", MessageType.CHAT.name)
        message_time = data.get("message_time")

        # Convert message_type string to numeric code for frontend
        message_type_enum = MessageType.from_name(message_type)
        if message_type_enum is None:
            logger.error("unknown_message_type_for_structured_message", message_type=message_type)
            raise ValueError(f"Unknown message type: {message_type}")
        message_type_code = message_type_enum.code

        # Validate required timestamp
        if not message_time:
            logger.error("missing_message_time", data=data)
            raise ValueError("message_time is required for structured messages")

        # Create structured message matching frontend types.js format
        structured_message = {
            "type": message_type_code,  # Numeric type (1=chat, 2=typing, etc.)
            "from": from_entity,
            "to": to_entity,
            "content": content,
            "timestamp": message_time,
            "service": 1,  # 1 = leancloud service
        }

        # Convert to JSON string for LeanCloud message field
        return json.dumps(structured_message)

    except Exception as e:
        logger.error("create_structured_message_failed", error=str(e), data=data, exc_info=True)
        # Don't fallback to plain content - structured messages are required
        raise


def send_system_conversation_message(
    conversation_id: str, from_peer: str, to_client: str, message_content: str
) -> dict:
    """
    Send a message through LeanMessage system conversation using REST API.
    Based on LeanCloud REST API documentation: 给任意用户单独发消息

    Args:
        conversation_id: LeanCloud conversation ID
        from_peer: Sender peer ID
        to_client: Target client ID
        message_content: Message content to send

    Returns:
        dict: Response from LeanCloud API

    Raises:
        RuntimeError: If API request fails
    """
    try:
        # REST API endpoint for sending system conversation message
        url = f"{settings.LEANCLOUD_BASE_URL}/1.2/rtm/service-conversations/{conversation_id}/messages"

        headers = {
            "X-LC-Id": settings.LEANCLOUD_APP_ID,
            "X-LC-Key": f"{settings.LEANCLOUD_MASTER_KEY},master",
            "Content-Type": "application/json",
        }

        # Message data following LeanCloud REST API format
        data = {
            "from_client": from_peer,  # Bot as sender
            "message": message_content,  # Plain text message
            "to_clients": [to_client],  # Send to specific client
        }

        logger.info(
            "sending_system_conversation_message",
            conversation_id=conversation_id,
            from_peer=from_peer,
            to_client=to_client,
            message_content=message_content,
            url=url,
        )

        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()

        result = response.json()
        logger.info(
            "system_conversation_message_sent",
            conversation_id=conversation_id,
            to_client=to_client,
            from_peer=from_peer,
            result=result,
        )

        return result

    except Exception as e:
        logger.error(
            "send_system_conversation_message_failed",
            error=str(e),
            conversation_id=conversation_id,
            to_client=to_client,
            from_peer=from_peer,
            exc_info=True,
        )
        raise RuntimeError(f"Failed to send system conversation message: {str(e)}")


# Message Sending Functions


async def send_leancloud_message(from_entity: str, to_entity: str, content: str, message_type: str) -> dict:
    """
    Send a message through LeanCloud message service.

    Args:
        from_entity: Sender entity ID
        to_entity: Receiver entity ID
        content: Message content
        message_type: Message type

    Returns:
        dict: Result of message sending operation

    Raises:
        ValueError: If parameters are invalid
        RuntimeError: If LeanCloud API fails
    """
    try:
        logger.info(
            "sending_leancloud_message",
            from_entity=from_entity,
            to_entity=to_entity,
            message_type=message_type,
        )

        # Validate required fields based on message type
        if not all([from_entity, to_entity]):
            raise ValueError("Missing required fields: from_entity, to_entity")

        # For typing messages, content can be empty, but for other messages, content is required
        if message_type not in [MessageType.TYPING.name, MessageType.TYPING_END.name]:
            if not content:
                raise ValueError("Content is required for non-typing messages")

        # Get conversation ID using cached function
        conversation_id = await get_cached_conversation_id()

        # Create structured message format for frontend
        structured_message = create_structured_message(
            {
                "from_entity": from_entity,
                "to_entity": to_entity,
                "content": content,
                "message_type": message_type,
                "message_time": datetime.now(timezone.utc).isoformat(),
            }
        )

        # Send through LeanCloud system conversation
        result = send_system_conversation_message(
            conversation_id=conversation_id,
            from_peer=from_entity,
            to_client=to_entity,
            message_content=structured_message,
        )

        logger.info(
            "leancloud_message_sent_successfully",
            from_entity=from_entity,
            to_entity=to_entity,
            message_type=message_type,
        )

        return result

    except Exception as e:
        logger.error("send_leancloud_message_failed", error=str(e), exc_info=True)
        raise RuntimeError(f"Failed to send LeanCloud message: {str(e)}")


async def send_system_message(
    from_entity: str,
    to_user: str,
    content: Dict[str, Any],
    message: Optional[str] = None,
) -> None:
    """
    Send system message to user

    Args:
        from_entity: Source entity ID (for chat window identification)
        to_user: Target user entity ID
        content: System message content dictionary
        message: Optional custom message text (overrides frontend default)
    """
    try:
        # Get conversation ID using cached function
        conversation_id = await get_cached_conversation_id()

        # Use provided content directly
        system_content = content.copy()

        # Add custom message if provided (overrides frontend default)
        if message:
            system_content["message"] = message

        # Create system message following backend message format
        system_message = {
            "id": f"system_{int(datetime.now().timestamp() * 1000)}",
            "type": MessageType.SYSTEM.code,  # Use numeric code (9)
            "from": from_entity,  # Source entity ID for chat window identification
            "to": to_user,
            "content": system_content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": 1,  # LeanCloud service
        }

        # Convert to JSON string for LeanCloud transport
        message_json = json.dumps(system_message)

        # Send through LeanCloud system conversation
        send_system_conversation_message(
            conversation_id=conversation_id,
            from_peer="system",
            to_client=to_user,
            message_content=message_json,
        )

        logger.info(
            "system_message_sent",
            from_entity=from_entity,
            to_user=to_user,
            content=system_content,
        )

    except Exception as e:
        logger.error(
            "send_system_message_failed",
            from_entity=from_entity,
            to_user=to_user,
            content=content,
            error=str(e),
            exc_info=True,
        )
        # Don't re-raise to avoid blocking main message flow


# Event Handler Functions


async def handle_send_message(data: dict) -> None:
    """
    Handle sending a message through LeanCloud.
    Event handler for SEND_MESSAGE events.

    Args:
        data: Message data from event bus
    """
    try:
        # Check the message service type, only process leancloud messages
        message_service = data.get("message_service")
        if message_service != IMServiceType.LEANCLOUD.value:
            logger.info("ignoring_non_leancloud_message", message_service=message_service)
            return

        from_entity = data.get("from_entity")
        to_entity = data.get("to_entity")
        content = data.get("content")
        message_type = data.get("message_type")

        # Validate required fields
        if not all([from_entity, to_entity, message_type]):
            logger.error("invalid_message_data_missing_required_fields", data=data)
            return

        # Send message using functional interface
        await send_leancloud_message(
            str(from_entity), str(to_entity), str(content) if content else "", str(message_type)
        )

    except Exception as e:
        logger.error("handle_send_message_failed", error=str(e), data=data, exc_info=True)


def setup_leancloud_handlers():
    """
    Set up LeanCloud message service event handlers.
    """
    try:
        # Subscribe to send message events
        event_bus.subscribe(EventTypes.SEND_MESSAGE, handle_send_message)
        logger.info("leancloud_event_handlers_setup")

    except Exception as e:
        logger.error("setup_leancloud_handlers_failed", error=str(e), exc_info=True)
        raise
