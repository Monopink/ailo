import asyncio
import random
from typing import Dict, Type, Optional, Any, Tuple
from enum import Enum, auto
from datetime import datetime
import time

from core.database import SessionLocal
from crud.bot import bot_crud
from crud.message import message_crud
from core.events import event_bus, EventTypes
from enums import (
    MessageType,
    MessageTypeCategory,
    BotStatus,
    SystemMessageStatus,
    SystemMessageReason,
    SystemMessageAction,
)
from exceptions import BotNotFoundError, AuthorizationError, DatabaseError
from utils.logging import get_logger

from .chat_models.base import BaseModel
from .chat_models.model_ailo import ModelAilo

logger = get_logger(__name__)


class ModelInstance:
    def __init__(self, model: BaseModel, message_service: str):
        self.model = model
        self.message_service = message_service


class ModelInstanceStatus(Enum):
    """Model instance status enum"""

    AVAILABLE = auto()
    SERVICE_MISMATCH = auto()
    NOT_FOUND = auto()


class MessageRouter:
    def __init__(self):
        self.model_registry: Dict[str, Type[BaseModel]] = {"ailo": ModelAilo}
        self.active_models: Dict[str, ModelInstance] = {}
        self.models_lock = asyncio.Lock()

        # Subscribe to message events
        event_bus.subscribe(EventTypes.RECEIVED_MESSAGE, self.handle_received_message)
        logger.info("message_router_initialized", subscriptions=["received_message"])

    def _validate_message(self, message: dict) -> bool:
        """Validate message format"""
        required_fields = [
            "from_entity",
            "to_entity",
            "message_type",
            "message_service",
        ]
        if not all(field in message for field in required_fields):
            logger.warning("message_missing_fields", message=message)
            return False
        return True

    async def save_message(self, message: dict) -> None:
        """Save message to database"""
        try:
            message_type_value = message.get("message_type")
            if not message_type_value:
                logger.warning("missing_message_type", message=message)
                return

            message_type = MessageType.parse(message_type_value)
            if message_type and message_type.category == MessageTypeCategory.CONTENT:
                async with SessionLocal() as db:
                    await message_crud.save_message(db, message)
                logger.info(
                    "message_saved", message_type=message_type.name, from_entity=message.get("from_entity")
                )
            else:
                logger.info(
                    "skipping_message_save",
                    message_type=str(message_type),
                    message_type_value=message_type_value,
                )
        except Exception as e:
            logger.error("message_save_error", error=str(e), exc_info=True)

    async def cleanup_model_instance(self, model_key: str) -> None:
        """Clean up model instance
        Args:
            model_key: Key of the model instance
        """
        try:
            async with self.models_lock:
                if model_key in self.active_models:
                    logger.info("cleaning_up_model", bot_entity_id=model_key)
                    # Remove from active instances dictionary
                    self.active_models.pop(model_key, None)
                    logger.info("model_cleanup_complete", bot_entity_id=model_key)
                else:
                    logger.warning("model_cleanup_not_found", bot_entity_id=model_key)

        except Exception as e:
            logger.error("model_cleanup_error", bot_entity_id=model_key, error=str(e), exc_info=True)

    def generate_message_id(self) -> str:
        """Generate unique message ID

        Returns:
            str: Unique message ID in format msg_{timestamp}_{random_string}
        """
        timestamp = int(datetime.now().timestamp() * 1000)  # milliseconds
        # Use same character set as entity_id generation for consistency
        chars = "23456789abcdefghjkmnpqrstuvwxyz"
        random_part = "".join(random.choices(chars, k=8))
        return f"msg_{timestamp}_{random_part}"

    async def handle_outgoing_message(self, message: dict) -> None:
        """Handle outgoing message processing

        This method processes messages being sent from bots to users.
        It generates message IDs, saves to database, and publishes to event bus.

        Args:
            message: Message dictionary containing message data
        """
        try:
            # Validate required fields
            if not self._validate_message(message):
                logger.error("invalid_outgoing_message", message=message)
                return

            # Generate unique message ID if not present
            if not message.get("message_id"):
                message["message_id"] = self.generate_message_id()
                logger.debug("generated_message_id", message_id=message["message_id"])

            # Publish to event bus for delivery
            await event_bus.publish(EventTypes.SEND_MESSAGE, message)

            # Save message to database
            await self.save_message(message)

            logger.info(
                "outgoing_message_processed",
                message_id=message.get("message_id"),
                from_entity=message.get("from_entity"),
                to_entity=message.get("to_entity"),
                message_type=message.get("message_type"),
            )

        except Exception as e:
            logger.error("outgoing_message_error", error=str(e), message=message, exc_info=True)

    def _validate_system_message_source(self, message: dict) -> bool:
        """
        Validate that system messages only come from authorized sources
        Simple MVP-level validation with architecture preparation for future security
        """
        if message.get("type") == MessageType.SYSTEM.code:
            # Check for internal source marker
            internal_source = message.get("_internal_source")
            if internal_source != "backend":
                logger.warning(
                    "unauthorized_system_message_attempt",
                    message_type=message.get("type"),
                    from_entity=message.get("from"),
                    internal_source=internal_source,
                )
                return False

            # Check timestamp for basic anti-replay (within 5 minutes)
            msg_timestamp = message.get("_timestamp")
            if msg_timestamp:
                current_time = time.time()
                if abs(current_time - msg_timestamp) > 300:  # 5 minutes
                    logger.warning(
                        "system_message_timestamp_invalid",
                        message_timestamp=msg_timestamp,
                        current_timestamp=current_time,
                        age_seconds=abs(current_time - msg_timestamp),
                    )
                    return False
        return True

    async def _send_system_message(
        self,
        from_bot: str,
        to_user: str,
        target_message_id_client: str,
        status: SystemMessageStatus,
        reason: SystemMessageReason,
        message: Optional[str] = None,
    ) -> None:
        """
        Send system message to notify user about message status changes

        Args:
            from_bot: Source bot entity ID (for chat window identification)
            to_user: Target user entity ID
            target_message_id_client: Client-side message ID that this system message refers to
            status: System message status (FAILED, BLOCKED, DELIVERED)
            reason: Failure reason numeric code (NOT_CONTACTS, USER_BLOCKED, etc.)
            message: Optional custom message text (overrides frontend default)
        """
        try:
            # Import here to avoid circular imports
            from .services.leanmessage import leanmessage_service

            # Create content for message status system message
            content = {
                "action": SystemMessageAction.MESSAGE_STATUS.value,  # 1
                "target_message_id": target_message_id_client,
                "status": status.value,  # 3, 4, 5
                "reason": reason.value,  # Numeric reason code (1-7) matching frontend
            }

            await leanmessage_service.send_system_message(
                from_entity=from_bot,
                to_user=to_user,
                content=content,
                message=message,
            )

            logger.info(
                "system_message_sent_from_router",
                to_user=to_user,
                target_message_id=target_message_id_client,
                status=status.value,
                reason=reason.value,
            )

        except Exception as e:
            logger.error(
                "send_system_message_from_router_failed",
                to_user=to_user,
                target_message_id=target_message_id_client,
                status=status.value if status else None,
                reason=reason.value if reason else None,
                error=str(e),
                exc_info=True,
            )
            # Don't re-raise to avoid blocking main message flow

    async def _verify_user_permission(self, user_entity_id: str, bot: Any) -> bool:
        """Verify user permission"""
        return not bot.user_entity_id or str(bot.user_entity_id) == user_entity_id

    async def _get_and_validate_bot(self, bot_entity_id: str, user_entity_id: str) -> Any:
        """
        Retrieves a bot from the database and validates user permissions.
        Raises specific exceptions if validation fails.
        """
        try:
            logger.info("querying_bot", bot_entity_id=bot_entity_id)
            async with SessionLocal() as db:
                bot = await bot_crud.get_by_entity_id(db, bot_entity_id)
            logger.info("bot_query_result", bot_entity_id=bot_entity_id, found=bot is not None)
            if not bot:
                raise BotNotFoundError(entity_id=bot_entity_id)

            if not await self._verify_user_permission(user_entity_id, bot):
                raise AuthorizationError(f"User {user_entity_id} not authorized for bot {bot_entity_id}")

            if bot.status != BotStatus.ACTIVE:
                # This could also be a specific exception if needed, e.g., BotInactiveError
                logger.warning("bot_inactive", bot_entity_id=bot_entity_id, status=bot.status)
                return None

            return bot
        except BotNotFoundError:
            # Re-raise to be handled by the FastAPI exception handler
            raise
        except AuthorizationError:
            # Re-raise
            raise
        except Exception as e:
            # Wrap other potential database/unexpected errors
            logger.error("bot_validation_error", bot_entity_id=bot_entity_id, error=str(e), exc_info=True)
            raise DatabaseError(f"An unexpected error occurred while retrieving bot {bot_entity_id}.")

    async def _create_model_instance(self, bot: Any, message_service: str) -> Optional[ModelInstance]:
        """Create new model instance

        Args:
            bot: Bot database object
            message_service: Message service type

        Returns:
            Optional[ModelInstance]: Created model instance, or None if creation failed
        """
        try:
            model_key = str(bot.entity_id)

            async with self.models_lock:
                # Create new instance
                model_class = self.model_registry.get(bot.model)
                if not model_class:
                    logger.error("unsupported_model", model_type=bot.model)
                    return None

                # Create model instance with async cleanup function and send message callback
                model = model_class(
                    bot=bot,
                    message_service=message_service,
                    cleanup_callback=self.cleanup_model_instance,
                    send_message_callback=self.handle_outgoing_message,
                )
                model_instance = ModelInstance(model, message_service)
                self.active_models[model_key] = model_instance
                logger.info("model_instance_created", bot_entity_id=model_key, model_type=bot.model)
                return model_instance

        except Exception as e:
            logger.error("model_creation_error", error=str(e), exc_info=True)
            return None

    async def _get_active_model_instance(
        self, bot_entity_id: str, message_service: str
    ) -> Tuple[ModelInstanceStatus, Optional[ModelInstance]]:
        """Get active model instance

        Args:
            bot_entity_id: Bot entity ID
            message_service: Message service type

        Returns:
            Tuple[ModelInstanceStatus, Optional[ModelInstance]]:
                - Status enum value
                - Model instance if status is AVAILABLE, otherwise None
        """
        async with self.models_lock:
            if bot_entity_id in self.active_models:
                instance = self.active_models[bot_entity_id]
                if instance.message_service == message_service:
                    return ModelInstanceStatus.AVAILABLE, instance
                else:
                    logger.warning(
                        "message_service_mismatch",
                        bot_entity_id=bot_entity_id,
                        expected_service=instance.message_service,
                        actual_service=message_service,
                    )
                    return ModelInstanceStatus.SERVICE_MISMATCH, None
        return ModelInstanceStatus.NOT_FOUND, None

    async def _route_message(self, message: dict) -> None:
        """Route message to appropriate model"""
        try:
            bot_entity_id = str(message["to_entity"])
            user_entity_id = str(message["from_entity"])
            message_service = message["message_service"]
            message_id_client = message.get(
                "message_id_client"
            )  # Frontend message ID for system message tracking

            # First try to get active model instance
            status, instance = await self._get_active_model_instance(bot_entity_id, message_service)

            if status == ModelInstanceStatus.AVAILABLE and instance is not None:
                # If matching instance found, send message
                await instance.model.receive_message(message)
                return
            elif status == ModelInstanceStatus.SERVICE_MISMATCH:
                # If service mismatch, return directly without creating new instance
                logger.warning("service_mismatch_skip_routing", bot_entity_id=bot_entity_id)
                return

            # Instance not found, create new instance and route message
            message_type_value = message["message_type"]
            message_type = MessageType.parse(message_type_value)
            logger.info(
                "parsing_message_type",
                message_type_value=message_type_value,
                parsed_type=str(message_type),
                category=message_type.category if message_type else None,
            )

            # Validate message type, return directly for non-content messages
            if not message_type or message_type.category != MessageTypeCategory.CONTENT:
                logger.warning(
                    "skipping_non_content_message",
                    message_type_value=message_type_value,
                    parsed_type=str(message_type),
                    category=message_type.category if message_type else None,
                )
                return

            # Get and validate bot
            bot = await self._get_and_validate_bot(bot_entity_id, user_entity_id)
            if not bot:
                # This case now only happens if the bot is inactive
                # Send system message to notify user that bot is not accepting messages
                if message_id_client:
                    asyncio.create_task(
                        self._send_system_message(
                            from_bot=bot_entity_id,
                            to_user=user_entity_id,
                            target_message_id_client=message_id_client,
                            status=SystemMessageStatus.FAILED,
                            reason=SystemMessageReason.USER_BLOCKED,
                        )
                    )
                return

            # Create new model instance
            model_instance = await self._create_model_instance(bot, message_service)
            if not model_instance:
                return

            # Send message to newly created model instance
            await model_instance.model.receive_message(message)

        except (BotNotFoundError, AuthorizationError, DatabaseError) as e:
            # These exceptions are now caught here and logged.
            # The FastAPI handler will ensure a proper HTTP response is sent if this was an API-triggered event.
            logger.error("message_routing_exception", error=e.detail)

            # Send system message to notify user about the failure
            if message_id_client:
                if isinstance(e, BotNotFoundError):
                    # Bot not found - treat as not contacts
                    asyncio.create_task(
                        self._send_system_message(
                            from_bot=bot_entity_id,
                            to_user=user_entity_id,
                            target_message_id_client=message_id_client,
                            status=SystemMessageStatus.FAILED,
                            reason=SystemMessageReason.NOT_CONTACTS,
                        )
                    )
                elif isinstance(e, AuthorizationError):
                    # User not authorized for this bot - treat as not contacts
                    asyncio.create_task(
                        self._send_system_message(
                            from_bot=bot_entity_id,
                            to_user=user_entity_id,
                            target_message_id_client=message_id_client,
                            status=SystemMessageStatus.FAILED,
                            reason=SystemMessageReason.NOT_CONTACTS,
                        )
                    )
                elif isinstance(e, DatabaseError):
                    # Database error - treat as system error
                    asyncio.create_task(
                        self._send_system_message(
                            from_bot=bot_entity_id,
                            to_user=user_entity_id,
                            target_message_id_client=message_id_client,
                            status=SystemMessageStatus.FAILED,
                            reason=SystemMessageReason.SYSTEM_ERROR,
                        )
                    )

        except Exception as e:
            logger.error("message_routing_error", error=str(e), exc_info=True)

            # Send system message for unexpected errors
            if message_id_client:
                asyncio.create_task(
                    self._send_system_message(
                        from_bot=bot_entity_id,
                        to_user=user_entity_id,
                        target_message_id_client=message_id_client,
                        status=SystemMessageStatus.FAILED,
                        reason=SystemMessageReason.SYSTEM_ERROR,
                    )
                )

    async def handle_received_message(self, message: dict) -> None:
        """Handle received message"""
        try:
            # Validate required message fields
            if not self._validate_message(message):
                raise ValueError("Invalid received message format")

            # Validate and route message
            asyncio.create_task(self._route_message(message))

            # Save message to database
            await self.save_message(message)

        except Exception as e:
            logger.error("received_message_error", error=str(e), exc_info=True)


# Create message router instance
message_router = MessageRouter()
