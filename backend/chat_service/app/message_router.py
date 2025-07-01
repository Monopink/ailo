import asyncio
from typing import Dict, Type, Optional, Any, Tuple
from enum import Enum, auto

from .db_managers import db_manager
from .event_bus import event_bus, EventTypes

from .models.base import BaseModel
from .models.model_ailo import ModelAilo
from .enums import MessageType, MessageTypeCategory, BotStatus
from .exceptions import BotNotFoundError, AuthorizationError, DatabaseError
from .utils.logging import get_logger

logger = get_logger("says.message_router")


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
        event_bus.subscribe(EventTypes.SEND_MESSAGE, self.handle_sent_message)
        logger.info("message_router_initialized", subscriptions=["received_message", "send_message"])

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
            message_type = MessageType.parse(str(message["message_type"]))
            if message_type and message_type.category == MessageTypeCategory.CONTENT:
                await db_manager.save_message(message)
            else:
                logger.info("skipping_message_save", message_type=str(message_type))
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

    async def _verify_user_permission(self, user_entity_id: str, bot: Any) -> bool:
        """Verify user permission"""
        return not bot.user_entity_id or str(bot.user_entity_id) == user_entity_id

    async def _get_and_validate_bot(self, bot_entity_id: str, user_entity_id: str) -> Any:
        """
        Retrieves a bot from the database and validates user permissions.
        Raises specific exceptions if validation fails.
        """
        try:
            bot = await db_manager.get_bot_by_entity_id(bot_entity_id)
            if not bot:
                raise BotNotFoundError(entity_id=bot_entity_id)

            if not await self._verify_user_permission(user_entity_id, bot):
                raise AuthorizationError(f"User {user_entity_id} not authorized for bot {bot_entity_id}")

            if bot.status != BotStatus.ACTIVE:
                # This could also be a specific exception if needed, e.g., BotInactiveError
                logger.info("bot_inactive", bot_entity_id=bot_entity_id, status=bot.status)
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

                # Create model instance with async cleanup function
                model = model_class(
                    bot=bot,
                    message_service=message_service,
                    cleanup_callback=self.cleanup_model_instance,
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
                    logger.info(
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
            message_type = MessageType.parse(str(message["message_type"]))
            # Validate message type, return directly for non-content messages
            if not message_type or message_type.category != MessageTypeCategory.CONTENT:
                logger.info("skipping_non_content_message", message_type=str(message_type))
                return

            # Get and validate bot
            bot = await self._get_and_validate_bot(bot_entity_id, user_entity_id)
            if not bot:
                # This case now only happens if the bot is inactive
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
        except Exception as e:
            logger.error("message_routing_error", error=str(e), exc_info=True)

    async def handle_sent_message(self, message: dict) -> None:
        """Handle sent message"""
        try:
            # Validate required message fields
            if not self._validate_message(message):
                raise ValueError("Invalid sent message format")

            await self.save_message(message)

        except Exception as e:
            logger.error("sent_message_error", error=str(e), exc_info=True)

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
