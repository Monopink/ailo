"""
LeanCloud Webhook Processing

Handles incoming webhook messages from LeanCloud and processes them for the application.
Provides message validation, parsing, and event publishing functionality.
"""

import json
from typing import Dict, Any, Optional
from fastapi import Request

from enums import MessageType, IMServiceType
from core.event_bus import event_bus, EventTypes
from utils.logging import get_logger
from .startup import get_cached_conversation_id

logger = get_logger(__name__)


# Message Processing Functions


def extract_basic_fields(message_data: Dict[str, Any]) -> tuple:
    """
    Extract and validate basic fields from LeanMessage webhook data.

    Args:
        message_data: Raw webhook message data

    Returns:
        tuple: (from_entity, conversation_id, message_content, msg_id, created_at)

    Raises:
        ValueError: If required fields are missing
    """
    from_entity = message_data.get("from")
    conv_info = message_data.get("conv", {})
    conversation_id = conv_info.get("objectId")
    message_content = message_data.get("data")
    msg_id = message_data.get("msgId")
    created_at = message_data.get("createdAt", {}).get("iso")

    if not all([from_entity, conversation_id, message_content]):
        raise ValueError("Missing required fields: from, conv.objectId, or data")

    return from_entity, conversation_id, message_content, msg_id, created_at


def extract_frontend_fields(structured_data: Optional[Dict[str, Any]]) -> tuple:
    """
    Extract frontend fields (from, to) from structured data.

    Args:
        structured_data: Parsed message data

    Returns:
        tuple: (frontend_from, frontend_to)
    """
    frontend_from = None
    frontend_to = None

    if structured_data and isinstance(structured_data, dict):
        # Check if structured_data contains frontend format directly
        if "from" in structured_data and "to" in structured_data:
            # Direct frontend format: {type: 2, from: "u1002", to: "b9002", ...}
            frontend_from = structured_data.get("from")
            frontend_to = structured_data.get("to")
        elif "_lctext" in structured_data:
            # LeanCloud format with _lctext, try to parse _lctext
            try:
                lctext_data = json.loads(structured_data["_lctext"])
                if isinstance(lctext_data, dict):
                    frontend_from = lctext_data.get("from")
                    frontend_to = lctext_data.get("to")
            except (json.JSONDecodeError, KeyError):
                # _lctext might contain plain text, skip parsing
                pass

    return frontend_from, frontend_to


def parse_leanmessage_content(content) -> tuple:
    """
    Parse LeanMessage message content and extract text and message type.

    Args:
        content: Raw message content from LeanCloud

    Returns:
        tuple: (content_text, message_type_code, structured_data)

    Raises:
        ValueError: If content format is invalid
    """
    try:
        # Handle both string and dict input
        if isinstance(content, str):
            # Try to parse as JSON (structured message format)
            if content.startswith("{"):
                parsed = json.loads(content)
            else:
                # Not JSON, reject
                raise ValueError("Message content must be in structured JSON format")
        elif isinstance(content, dict):
            # Already parsed dict (from LeanCloud data field)
            parsed = content
        else:
            raise ValueError("Invalid content type")

        # Check if this is LeanCloud wrapper format
        if isinstance(parsed, dict) and "_lctext" in parsed:
            # Extract the actual message from _lctext
            lctext_content = parsed.get("_lctext", "")
            if lctext_content:
                try:
                    # Parse the inner JSON
                    parsed = json.loads(lctext_content)
                except json.JSONDecodeError:
                    logger.error("invalid_lctext_not_json", lctext_content=lctext_content[:100])
                    raise ValueError("_lctext must be valid JSON")
            else:
                raise ValueError("_lctext must contain structured message format")

        # Now we have the actual message content in parsed
        if isinstance(parsed, dict):
            # Check for new frontend format with numeric 'type' field
            if "type" in parsed:
                # New frontend format: {type: 2, from: 'u1001', to: 'u1002', content: '', ...}
                # Extract the actual content from the (possibly decrypted) JSON structure
                content_text = parsed.get("content", "")
                frontend_message_type = parsed.get("type")

                # Convert frontend numeric type to backend enum code
                if isinstance(frontend_message_type, int):
                    message_type_enum = MessageType.from_code(frontend_message_type)
                else:
                    message_type_enum = MessageType.from_name(str(frontend_message_type))

                if message_type_enum is None:
                    logger.warning("unknown_message_type", type_value=frontend_message_type)
                    message_type_code = MessageType.CHAT.code
                else:
                    message_type_code = message_type_enum.code

                # For typing messages, return empty content
                if message_type_code in [MessageType.TYPING.code, MessageType.TYPING_END.code]:
                    return "", message_type_code, parsed
                else:
                    return content_text, message_type_code, parsed

            elif "_lctext" in parsed:
                # Extract text from LeanMessage native format and try to parse it further
                lctext_content = parsed["_lctext"]

                # Try to parse _lctext as JSON (it might contain our structured message)
                try:
                    lctext_parsed = json.loads(lctext_content)

                    # Check if _lctext contains our new frontend format
                    if isinstance(lctext_parsed, dict) and "type" in lctext_parsed:
                        # This is our structured message inside _lctext
                        content_text = lctext_parsed.get("content", "")
                        frontend_message_type = lctext_parsed.get("type")

                        # Convert frontend numeric type to backend enum code
                        if isinstance(frontend_message_type, int):
                            message_type_enum = MessageType.from_code(frontend_message_type)
                        else:
                            message_type_enum = MessageType.from_name(str(frontend_message_type))

                        if message_type_enum is None:
                            logger.error(
                                "unknown_message_type_in_lctext",
                                type_value=frontend_message_type,
                            )
                            raise ValueError(f"Unknown message type in _lctext: {frontend_message_type}")
                        message_type_code = message_type_enum.code

                        # For typing messages, return empty content
                        if message_type_code in [
                            MessageType.TYPING.code,
                            MessageType.TYPING_END.code,
                        ]:
                            return "", message_type_code, lctext_parsed
                        else:
                            return content_text, message_type_code, lctext_parsed
                    else:
                        # _lctext doesn't contain structured format
                        logger.error("invalid_lctext_format", lctext_content=lctext_content[:100])
                        raise ValueError("_lctext must contain structured message format")
                except json.JSONDecodeError:
                    # _lctext is not JSON - reject
                    logger.error("invalid_lctext_not_json", lctext_content=lctext_content[:100])
                    raise ValueError("_lctext must be valid JSON")
            else:
                # No _lctext found, invalid format
                logger.error("missing_lctext_in_leancloud_format")
                raise ValueError("LeanCloud format must contain _lctext field")
        else:
            # Not a dict, invalid format
            logger.error("invalid_parsed_format", parsed_type=type(parsed))
            raise ValueError("Parsed content must be a dictionary")

    except Exception as e:
        logger.error("content_parsing_failed", error=str(e), content=str(content)[:100])
        raise


def validate_message_structure(message_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and convert LeanMessage message to backend format according to enums.py

    Args:
        message_data: Raw LeanMessage webhook data

    Returns:
        dict: Structured message in backend format

    Raises:
        ValueError: If message data is invalid
    """
    try:
        # Extract basic fields
        from_entity, conversation_id, message_content, msg_id, created_at = extract_basic_fields(
            message_data
        )

        # Parse message content and extract message type
        parsed_content, message_type, structured_data = parse_leanmessage_content(str(message_content))

        # Extract frontend fields from structured data
        frontend_from, frontend_to = extract_frontend_fields(structured_data)

        # Extract message_id_client from structured data (frontend message ID)
        message_id_client = None
        if structured_data and isinstance(structured_data, dict):
            message_id_client = structured_data.get("id")  # Frontend uses 'id' field

        # Create message_metadata for non-standard fields
        message_metadata = {
            "conversation_id": conversation_id,
            "external_msg_id": msg_id,
        }

        # Add frontend-specific fields to metadata if available
        if structured_data and isinstance(structured_data, dict):
            frontend_fields = {
                "timestamp": structured_data.get("timestamp"),
                "service": structured_data.get("service"),
            }
            # Only add non-None values
            message_metadata.update({k: v for k, v in frontend_fields.items() if v is not None})

        # Validate required timestamp
        if not created_at:
            logger.error("missing_created_at_timestamp", message_data=message_data)
            raise ValueError("createdAt timestamp is required")

        # Create structured message according to enums.py format
        structured_message = {
            "from_entity": frontend_from or from_entity,  # Prefer frontend field
            "to_entity": frontend_to,  # Will be set later if None
            "content": parsed_content,
            "message_type": message_type,
            "message_service": IMServiceType.LEANCLOUD.value,
            "message_time": created_at,
            "message_id_client": message_id_client,  # Frontend message ID for tracking
            "message_metadata": message_metadata,
        }

        return structured_message

    except Exception as e:
        logger.error("message_validation_failed", error=str(e), message_data=message_data, exc_info=True)
        raise


# Webhook Handler Functions


async def handle_leancloud_message_webhook(request: Request) -> Dict[str, str]:
    """
    Handle LeanMessage webhook for incoming messages from system conversations.

    LeanMessage sends webhook data in this format:
    [
        {
            "fromIp": "192.168.1.100",
            "conv": {"__type": "Pointer", "className": "_Conversation", "objectId": "abc123def456ghi789"},
            "msgId": "msg_12345abcdef",
            "from": "user_123",
            "bin": false,
            "data": "Hello, this is a test message",
            "createdAt": {"__type": "Date", "iso": "2023-12-01T08:30:00.000Z"},
            "updatedAt": {"__type": "Date", "iso": "2023-12-01T08:30:00.000Z"}
        }
    ]
    """
    try:
        # Get raw body
        body = await request.body()
        messages = json.loads(body.decode("utf-8"))

        logger.info("leanmessage_webhook_received", data=messages)

        # Process each message
        for message_data in messages:
            await process_leancloud_webhook_message(message_data)

        return {"status": "ok"}

    except Exception as e:
        logger.error("leanmessage_webhook_error", error=str(e), exc_info=True)
        return {"status": "error", "message": str(e)}


async def process_leancloud_webhook_message(message_data: Dict[str, Any]) -> dict:
    """
    Process a single LeanMessage webhook message.

    Args:
        message_data: Raw webhook message data from LeanCloud

    Returns:
        dict: Processed message result

    Raises:
        ValueError: If message data is invalid
    """
    try:
        logger.info("processing_webhook_message", message_data=message_data)

        # Validate basic message structure
        if not isinstance(message_data, dict):
            logger.error("invalid_webhook_message_format", message_data=message_data)
            raise ValueError("Invalid webhook message format")

        # Validate and structure the message
        structured_message = validate_message_structure(message_data)

        if not structured_message:
            logger.error("failed_to_validate_message_structure", message_data=message_data)
            raise ValueError("Failed to validate message structure")

        # In unified conversation architecture, bot entity_id is already in the message content
        # Validate that we have the required to_entity field
        bot_entity_id = structured_message.get("to_entity")
        if not bot_entity_id:
            logger.error(
                "missing_to_entity_in_message",
                structured_message=structured_message,
            )
            raise ValueError("Missing to_entity in message")

        # Validate that the conversation_id matches our unified conversation
        message_metadata = structured_message.get("message_metadata", {})
        conversation_id = message_metadata.get("conversation_id")
        if conversation_id:
            try:
                expected_conversation_id = await get_cached_conversation_id()
                if conversation_id != expected_conversation_id:
                    logger.warning(
                        "conversation_id_mismatch",
                        received=conversation_id,
                        expected=expected_conversation_id,
                    )
            except ValueError:
                logger.warning("leancloud_conversation_id_not_configured")

        # Log the complete structured message
        logger.info(
            "complete_structured_message",
            structured_message=structured_message,
            from_entity=structured_message.get("from_entity"),
            to_entity=structured_message.get("to_entity"),
            message_type=structured_message.get("message_type"),
            content=structured_message.get("content"),
        )

        # Publish to event bus for further processing
        await event_bus.publish(EventTypes.RECEIVED_MESSAGE, structured_message)

        logger.info(
            "webhook_message_processed",
            from_entity=structured_message.get("from_entity"),
            to_entity=structured_message.get("to_entity"),
            msg_id=structured_message.get("external_msg_id"),
        )

        return {"status": "success", "message": "Webhook message processed successfully"}

    except Exception as e:
        logger.error(
            "webhook_message_processing_failed", error=str(e), message_data=message_data, exc_info=True
        )
        raise RuntimeError(f"Failed to process webhook message: {str(e)}")
