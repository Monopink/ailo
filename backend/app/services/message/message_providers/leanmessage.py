import json
import requests
import threading
from typing import Dict, Any, Optional
from datetime import datetime, timezone

# import leancloud  # Commented out - using REST API only
from core.config import settings
from enums import MessageType, IMServiceType
from core.events import event_bus, EventTypes
from utils.logging import get_logger

from .leancloud.config_manager import get_unified_conversation_id
from .encryption import encryption_service

logger = get_logger(__name__)


class LeanMessageManager:
    """Thread-safe singleton LeanMessage manager"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # Only initialize once
        if hasattr(self, "_initialized"):
            return

        self._initialized = False
        self._server_client = None  # Server's LeanMessage client
        self._server_id = "says"  # ID for the server in LeanMessage
        self._conversations = {}  # Cache for conversations

    def init_rest_api(self):
        """
        Initialize the LeanMessage REST API client.
        No SDK required - using pure REST API.
        """
        if self._initialized:
            return

        app_id = settings.LEANCLOUD_APP_ID
        master_key = settings.LEANCLOUD_MASTER_KEY
        base_url = settings.LEANCLOUD_BASE_URL

        if not app_id or not master_key or not base_url:
            logger.error("leanmessage_credentials_missing")
            raise ValueError("LEANCLOUD_APP_ID, LEANCLOUD_MASTER_KEY and LEANCLOUD_BASE_URL must be set")

        try:
            # Validate credentials by testing API access
            self._validate_api_credentials()

            self._initialized = True
            logger.info("leanmessage_rest_api_initialized")

            # Initialize server client for sending messages
            self._init_server_client()
        except Exception as e:
            logger.error("leanmessage_rest_api_init_failed", error=str(e), exc_info=True)
            raise

    def _validate_api_credentials(self):
        """
        Validate LeanCloud API credentials by making a test request.
        """
        try:
            # Test API access by querying service conversations
            url = f"{settings.LEANCLOUD_BASE_URL}/1.2/rtm/service-conversations"
            headers = {
                "X-LC-Id": settings.LEANCLOUD_APP_ID,
                "X-LC-Key": f"{settings.LEANCLOUD_MASTER_KEY},master",
                "Content-Type": "application/json",
            }

            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code in [200, 404]:  # 404 is OK if no conversations exist
                logger.info("leancloud_api_credentials_validated")
            else:
                raise ValueError(f"API validation failed with status {response.status_code}")

        except requests.RequestException as e:
            logger.error("leancloud_api_validation_failed", error=str(e))
            raise ValueError(f"Failed to validate LeanCloud API credentials: {str(e)}")

    def _init_server_client(self):
        """
        Initialize the server client for LeanMessage.
        This creates a special client that represents the server in conversations.
        """
        try:
            # Using the Realtime SDK via the Python REST API wrapper
            # Note: This is a workaround since the Python SDK doesn't have a native Realtime client
            # For production, consider using webhooks or other integration methods

            # Mark as initialized - in a real implementation, we would initialize
            # a proper LeanMessage client for the server
            self._server_client = True
            logger.info("server_client_initialized", server_id=self._server_id)
        except Exception as e:
            logger.error("server_client_init_failed", error=str(e), exc_info=True)
            raise

    async def handle_send_message(self, data):
        """
        Handle sending a message through LeanMessage.
        This sends a message from the server to a user.
        """
        if not self._initialized:
            logger.warning("leanmessage_sdk_not_initialized")
            return

        logger.info("handle_send_message_called", data=data)

        # Check the message service type, only process leancloud messages
        message_service = data.get("message_service")
        if message_service != IMServiceType.LEANCLOUD.value:
            logger.info("ignoring_non_leancloud_message", message_service=message_service)
            return

        from_entity = data.get("from_entity")
        to_entity = data.get("to_entity")
        content = data.get("content")
        message_type = data.get("message_type")

        # Validate required fields based on message type
        if not all([from_entity, to_entity]):
            logger.error("invalid_message_data_missing_entities", data=data)
            return

        # For typing messages, content can be empty, but for other messages, content is required
        if message_type not in [MessageType.TYPING.name, MessageType.TYPING_END.name]:
            if not content:
                logger.error("invalid_message_data_missing_content", data=data)
                return

        try:
            # Use unified system conversation ID for all bot messages
            conversation_id = get_unified_conversation_id()

            # Create structured message format for frontend
            structured_message = self._create_structured_message(data)

            self._send_system_conversation_message(
                conversation_id=conversation_id,
                from_peer=from_entity,
                to_client=to_entity,
                message_content=structured_message,
            )
            logger.info(
                "message_sent_successfully",
                from_entity=from_entity,
                to_entity=to_entity,
                message_type=message_type,
            )

        except Exception as e:
            logger.error("leanmessage_send_message_failed", error=str(e), exc_info=True)

    def _create_structured_message(self, data: Dict[str, Any]) -> str:
        """
        Create structured message format for frontend consumption.
        This wraps the message data in the format expected by frontend.
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

            # Encrypt message content before sending
            try:
                encrypted_message = encryption_service.encrypt_message(structured_message)
            except Exception as e:
                logger.error("message_encryption_failed", error=str(e), exc_info=True)
                raise

            # Convert to JSON string for LeanCloud message field
            return json.dumps(encrypted_message)

        except Exception as e:
            logger.error("create_structured_message_failed", error=str(e), data=data, exc_info=True)
            # Don't fallback to plain content - structured messages are required
            raise

    def _send_system_conversation_message(
        self, conversation_id: str, from_peer: str, to_client: str, message_content: str
    ):
        """
        Send a message through LeanMessage system conversation using REST API.
        Based on LeanCloud REST API documentation: 给任意用户单独发消息
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

        except Exception as e:
            logger.error(
                "send_system_conversation_message_failed",
                error=str(e),
                conversation_id=conversation_id,
                to_client=to_client,
                from_peer=from_peer,
                exc_info=True,
            )
            raise

    async def send_system_message(
        self,
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
            # Get unified conversation ID
            conversation_id = get_unified_conversation_id()

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
            self._send_system_conversation_message(
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

    def _extract_basic_fields(self, message_data: Dict[str, Any]) -> tuple:
        """Extract and validate basic fields from LeanMessage webhook data."""
        from_entity = message_data.get("from")
        conv_info = message_data.get("conv", {})
        conversation_id = conv_info.get("objectId")
        message_content = message_data.get("data")
        msg_id = message_data.get("msgId")
        created_at = message_data.get("createdAt", {}).get("iso")

        if not all([from_entity, conversation_id, message_content]):
            raise ValueError("Missing required fields: from, conv.objectId, or data")

        return from_entity, conversation_id, message_content, msg_id, created_at

    def _extract_frontend_fields(self, structured_data: Optional[Dict[str, Any]]) -> tuple:
        """Extract frontend fields (from, to) from structured data."""
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

    def validate_message_structure(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and convert LeanMessage message to backend format according to enums.py
        """
        try:
            # Extract basic fields
            from_entity, conversation_id, message_content, msg_id, created_at = self._extract_basic_fields(
                message_data
            )

            # Input validation logging removed for cleaner logs

            # Parse message content and extract message type
            parsed_content, message_type, structured_data = self._parse_leanmessage_content(
                str(message_content)
            )

            # Extract frontend fields from structured data
            frontend_from, frontend_to = self._extract_frontend_fields(structured_data)

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
            logger.error(
                "message_validation_failed", error=str(e), message_data=message_data, exc_info=True
            )
            raise

    def _parse_leanmessage_content(self, content) -> tuple:
        """
        Parse LeanMessage message content and extract text and message type.
        Returns: (content_text, message_type_code, structured_data)
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
                # Check if message is encrypted and decrypt it
                if encryption_service.is_encrypted(parsed):
                    try:
                        parsed = encryption_service.decrypt_message(parsed)
                    except Exception as e:
                        logger.error("message_decryption_failed", error=str(e), exc_info=True)
                        raise

                # Check for new frontend format with numeric 'type' field
                if "type" in parsed:
                    # New frontend format: {type: 2, from: 'u1001', to: 'u1002', content: '', ...}
                    # Extract the actual content from the (possibly decrypted) JSON structure
                    content_text = parsed.get("content", "")
                    frontend_message_type = parsed.get("type")

                    # Frontend format detected

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

                    # Type conversion completed

                    # For typing messages, return empty content
                    if message_type_code in [MessageType.TYPING.code, MessageType.TYPING_END.code]:
                        return "", message_type_code, parsed
                    else:
                        return content_text, message_type_code, parsed

                # Old message_type string format is no longer supported

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

                            # Frontend format detected in _lctext

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
                                raise ValueError(
                                    f"Unknown message type in _lctext: {frontend_message_type}"
                                )
                            message_type_code = message_type_enum.code

                            # Type conversion from _lctext completed

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
            logger.error("content_parsing_failed", error=str(e), content=content[:100])
            raise

    async def process_webhook_message(self, message_data: Dict[str, Any]) -> None:
        """
        Process a single LeanMessage webhook message.
        """
        try:
            logger.info("processing_webhook_message", message_data=message_data)

            # Validate basic message structure
            if not isinstance(message_data, dict):
                logger.error("invalid_webhook_message_format", message_data=message_data)
                return

            # Validate and structure the message
            structured_message = self.validate_message_structure(message_data)

            if not structured_message:
                logger.error("failed_to_validate_message_structure", message_data=message_data)
                return

            # In unified conversation architecture, bot entity_id is already in the message content
            # Validate that we have the required to_entity field
            bot_entity_id = structured_message.get("to_entity")
            if not bot_entity_id:
                logger.error(
                    "missing_to_entity_in_message",
                    structured_message=structured_message,
                )
                return

            # Validate that the conversation_id matches our unified conversation
            message_metadata = structured_message.get("message_metadata", {})
            conversation_id = message_metadata.get("conversation_id")
            if conversation_id:
                try:
                    expected_conversation_id = get_unified_conversation_id()
                    if conversation_id != expected_conversation_id:
                        logger.warning(
                            "conversation_id_mismatch",
                            received=conversation_id,
                            expected=expected_conversation_id,
                        )
                except ValueError:
                    logger.warning("unified_conversation_id_not_configured")

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

        except Exception as e:
            logger.error(
                "webhook_message_processing_failed", error=str(e), message_data=message_data, exc_info=True
            )


# Create global leanmessage service instance
leanmessage_service = LeanMessageManager()


def setup_leanmessage_handlers():
    """
    Set up LeanMessage service and event handlers.
    """
    leanmessage_service.init_rest_api()

    # Subscribe to an event that triggers sending a message
    event_bus.subscribe(EventTypes.SEND_MESSAGE, leanmessage_service.handle_send_message)
    logger.info("leanmessage_event_handlers_setup")


# You might want to call setup_leanmessage_handlers() at application startup.
# For example, in your main application file where you create the FastAPI app.
