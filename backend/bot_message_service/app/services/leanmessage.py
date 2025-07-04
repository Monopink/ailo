import json
import requests
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import leancloud
from ..event_bus import event_bus, EventTypes
from ..utils.logging import get_logger
from ..core.config import settings
from ..enums import MessageType
from ..database import SessionLocal, bot_crud

logger = get_logger(__name__)


class LeanMessageManager:
    def __init__(self):
        self._initialized = False
        self._server_client = None  # Server's LeanMessage client
        self._server_id = "says_server"  # ID for the server in LeanMessage
        self._conversations = {}  # Cache for conversations

    def init_sdk(self):
        """
        Initialize the LeanMessage SDK.
        """
        if self._initialized:
            return

        app_id = settings.LEANCLOUD_APP_ID
        app_key = settings.LEANCLOUD_APP_KEY
        master_key = settings.LEANCLOUD_MASTER_KEY
        region = settings.LEANCLOUD_SERVER_URL  # Now this should be 'CN' or 'US'

        if not app_id or not app_key or not master_key:
            logger.error("leanmessage_credentials_missing")
            raise ValueError("LEANCLOUD_APP_ID, LEANCLOUD_APP_KEY and LEANCLOUD_MASTER_KEY must be set")

        try:
            # Initialize LeanCloud SDK
            # pylint: disable=no-member
            leancloud.init(app_id, app_key=app_key, master_key=master_key)

            # Handle region setting correctly
            if region:
                logger.info(f"Setting LeanMessage region to: {region}")

                # Use the correct region code (CN or US)
                if region.upper() == "CN":
                    # pylint: disable=no-member
                    leancloud.use_region("CN")
                elif region.upper() == "US":
                    # pylint: disable=no-member
                    leancloud.use_region("US")
                else:
                    logger.warning(f"Unknown region: {region}, defaulting to CN")
                    # pylint: disable=no-member
                    leancloud.use_region("CN")

            self._initialized = True
            logger.info("leanmessage_sdk_initialized")

            # Initialize server client for sending messages
            self._init_server_client()
        except Exception as e:
            logger.error("leanmessage_sdk_init_failed", error=str(e), exc_info=True)
            raise

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

        from_entity = data.get("from_entity")
        to_entity = data.get("to_entity")
        content = data.get("content")

        if not all([from_entity, to_entity, content]):
            logger.error("invalid_message_data", data=data)
            return

        try:
            # Get conversation_id from data, or look it up from bot entity_id
            conversation_id = data.get("conversation_id")
            if not conversation_id:
                # Look up conversation_id from bot entity_id
                conversation_id = await self._get_conversation_id_from_bot(from_entity)
                if not conversation_id:
                    logger.error("missing_conversation_id", data=data)
                    return

            self._send_system_conversation_message(
                conversation_id=conversation_id,
                from_peer=from_entity,
                to_client=to_entity,
                message_content=content,
            )
            logger.info("message_sent_successfully", from_entity=from_entity, to_entity=to_entity)

        except Exception as e:
            logger.error("leanmessage_send_message_failed", error=str(e), exc_info=True)

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

    async def get_bot_entity_from_conversation(self, conversation_id: str) -> str:
        """
        Get bot entity_id from LeanMessage conversation ID by querying the database.
        """
        try:
            # Query the database to find the bot with this conversation_id from conversation_mappings
            async with SessionLocal() as db:
                bot_entity_id = await bot_crud.get_bot_by_conversation_id(db, conversation_id)

            if bot_entity_id:
                logger.info(
                    "bot_found_for_conversation",
                    conversation_id=conversation_id,
                    bot_entity_id=bot_entity_id,
                )
                return bot_entity_id
            else:
                logger.warning("no_bot_found_for_conversation", conversation_id=conversation_id)
                return "b9002"  # Default fallback

        except Exception as e:
            logger.error("get_bot_entity_error", error=str(e), conversation_id=conversation_id)
            return "b9002"  # Default fallback

    async def _get_conversation_id_from_bot(self, bot_entity_id: str) -> Optional[str]:
        """
        Get LeanMessage conversation ID from bot entity_id by querying the database.
        """
        try:
            # Query the database to find the conversation_id for this bot from conversation_mappings
            async with SessionLocal() as db:
                conversation_id = await bot_crud.get_conversation_id_by_bot(db, bot_entity_id)

            if conversation_id:
                logger.info(
                    "conversation_found_for_bot",
                    bot_entity_id=bot_entity_id,
                    conversation_id=conversation_id,
                )
                return conversation_id
            else:
                logger.warning("no_conversation_found_for_bot", bot_entity_id=bot_entity_id)
                return None

        except Exception as e:
            logger.error("get_conversation_id_error", error=str(e), bot_entity_id=bot_entity_id)
            return None

    def validate_message_structure(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and convert LeanMessage message to bot_message_service format according to enums.py
        """
        try:
            # Extract basic fields
            from_entity = message_data.get("from")
            conv_info = message_data.get("conv", {})
            conversation_id = conv_info.get("objectId")
            message_content = message_data.get("data")
            msg_id = message_data.get("msgId")
            created_at = message_data.get("createdAt", {}).get("iso")

            if not all([from_entity, conversation_id, message_content]):
                raise ValueError("Missing required fields: from, conv.objectId, or data")

            # Parse message content and extract message type
            parsed_content, message_type, _ = self._parse_leanmessage_content(str(message_content))

            # Create structured message according to enums.py format
            structured_message = {
                "from_entity": from_entity,
                "to_entity": None,  # Will be set later
                "content": parsed_content,
                "message_type": message_type,
                "message_service": "leancloud",
                "message_time": created_at or datetime.now(timezone.utc).isoformat(),
                "conversation_id": conversation_id,
                "external_msg_id": msg_id,
            }

            logger.info("message_structure_validated", structured_message=structured_message)
            return structured_message

        except Exception as e:
            logger.error("message_validation_failed", error=str(e), message_data=message_data)
            raise

    def _parse_leanmessage_content(self, content: str) -> tuple:
        """
        Parse LeanMessage message content and extract text and message type.
        Returns: (content_text, message_type_code, structured_data)
        """
        try:
            # Try to parse as JSON (structured message format)
            if content.startswith("{"):
                parsed = json.loads(content)
                if isinstance(parsed, dict):
                    # Check if it's our structured message format
                    if "message_type" in parsed:
                        # This is our structured message format from frontend
                        content_text = parsed.get("content", "")
                        frontend_message_type = parsed.get("message_type", "chat")

                        # Convert frontend string type to backend enum code
                        message_type_enum = MessageType.from_name(frontend_message_type)
                        if message_type_enum is None:
                            message_type_code = MessageType.CHAT.code
                        else:
                            message_type_code = message_type_enum.code

                        return content_text, message_type_code, parsed
                    elif "_lctext" in parsed:
                        # Extract text from LeanMessage native format
                        return parsed["_lctext"], MessageType.CHAT.code, parsed
                    elif "text" in parsed:
                        return parsed["text"], MessageType.CHAT.code, parsed
                    else:
                        # Return the whole object as string if no recognized format
                        return str(parsed), MessageType.CHAT.code, parsed

            # Return as plain text if not JSON
            return content, MessageType.CHAT.code, None

        except json.JSONDecodeError:
            # Return as plain text if JSON parsing fails
            return content, MessageType.CHAT.code, None
        except Exception as e:
            logger.error("content_parsing_failed", error=str(e), content=content)
            return content, MessageType.CHAT.code, None

    async def process_webhook_message(self, message_data: Dict[str, Any]) -> None:
        """
        Process a single LeanMessage webhook message.
        """
        try:
            # Validate and structure the message
            structured_message = self.validate_message_structure(message_data)

            # Get bot entity_id from conversation
            conversation_id = structured_message.get("conversation_id")
            if conversation_id:
                bot_entity_id = await self.get_bot_entity_from_conversation(conversation_id)
                structured_message["to_entity"] = bot_entity_id

            # Publish to event bus for further processing
            await event_bus.publish(EventTypes.RECEIVED_MESSAGE, structured_message)

            logger.info(
                "webhook_message_processed",
                from_entity=structured_message.get("from_entity"),
                to_entity=structured_message.get("to_entity"),
                msg_id=structured_message.get("external_msg_id"),
            )

        except Exception as e:
            logger.error("webhook_message_processing_failed", error=str(e), message_data=message_data)


# Create global leanmessage service instance
leanmessage_service = LeanMessageManager()


def setup_leanmessage_handlers():
    """
    Set up LeanMessage service and event handlers.
    """
    leanmessage_service.init_sdk()

    # Subscribe to an event that triggers sending a message
    event_bus.subscribe(EventTypes.SEND_MESSAGE, leanmessage_service.handle_send_message)
    logger.info("leanmessage_event_handlers_setup")


# You might want to call setup_leanmessage_handlers() at application startup.
# For example, in your main application file where you create the FastAPI app.
