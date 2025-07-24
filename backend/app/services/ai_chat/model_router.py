import asyncio
from typing import Dict, Type, Optional, Any, Tuple
from enum import Enum, auto

from core.database import SessionLocal
from repositories.bot import BotRepository
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
from services.message.message import send_system_message

from .models.base import BaseModel
from .models.model_ailo import ModelAilo

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


class ModelRouter:
    def __init__(self):
        self.model_registry: Dict[str, Type[BaseModel]] = {"ailo": ModelAilo}
        self.active_models: Dict[str, ModelInstance] = {}
        self.models_lock = asyncio.Lock()

        logger.info("model_router_initialized")

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
            logger.info("querying_bot", bot_entity_id=bot_entity_id)
            # Use repository layer with centralized session management
            async with SessionLocal() as db:
                bot_repository = BotRepository()
                bot = await bot_repository.get_by_entity_id(db, bot_entity_id)
            logger.info("bot_query_result", bot_entity_id=bot_entity_id, found=bot is not None)
            if not bot:
                raise BotNotFoundError(entity_id=bot_entity_id)
            if not await self._verify_user_permission(user_entity_id, bot):
                raise AuthorizationError(f"User {user_entity_id} not authorized for bot {bot_entity_id}")
            if bot.status != BotStatus.ACTIVE:
                logger.warning("bot_inactive", bot_entity_id=bot_entity_id, status=bot.status)
                return None

            return bot
        except (BotNotFoundError, AuthorizationError):
            # Re-raise these exceptions to be handled by the unified error handler
            raise
        except Exception as e:
            logger.error("bot_access_error", bot_entity_id=bot_entity_id, error=str(e), exc_info=True)
            raise DatabaseError(f"Error accessing bot {bot_entity_id}")

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
                # Bot is inactive - send unified error message
                if message_id_client:
                    asyncio.create_task(
                        send_system_message(
                            from_entity=bot_entity_id,
                            to_entity=user_entity_id,
                            action=SystemMessageAction.MESSAGE_STATUS,
                            target_message_id=message_id_client,
                            status=SystemMessageStatus.FAILED,
                            reason=SystemMessageReason.SYSTEM_ERROR,  # Using a more generic reason
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
            # Unified exception handling for all application-level exceptions
            logger.error("message_routing_error", error=str(e))

            # Send system message to notify user about the failure
            if message_id_client:
                # Determine appropriate reason based on exception type
                reason = SystemMessageReason.SYSTEM_ERROR  # Default reason

                # Map exception types to appropriate reasons
                if isinstance(e, (BotNotFoundError, AuthorizationError)):
                    reason = SystemMessageReason.NOT_CONTACTS

                # Send unified system message
                asyncio.create_task(
                    send_system_message(
                        from_entity=bot_entity_id,
                        to_entity=user_entity_id,
                        action=SystemMessageAction.MESSAGE_STATUS,
                        target_message_id=message_id_client,
                        status=SystemMessageStatus.FAILED,
                        reason=reason,
                    )
                )

        except Exception as e:
            # Unified error handling for all unexpected exceptions
            logger.error("message_routing_error", error=str(e), exc_info=True)

            # Send unified system message for all unexpected errors
            if message_id_client:
                asyncio.create_task(
                    send_system_message(
                        from_entity=bot_entity_id,
                        to_entity=user_entity_id,
                        action=SystemMessageAction.MESSAGE_STATUS,
                        target_message_id=message_id_client,
                        status=SystemMessageStatus.FAILED,
                        reason=SystemMessageReason.SYSTEM_ERROR,
                    )
                )

    async def route_message(self, message: dict) -> None:
        """
        Public method for routing messages to AI models
        Called directly by message.py after message processing

        Args:
            message: Message dictionary to route
        """
        try:
            # Route message to appropriate model
            await self._route_message(message)

        except Exception as e:
            # Unified error handling
            logger.error("message_routing_error", error=str(e), exc_info=True)


# Create model router instance
model_router = ModelRouter()
