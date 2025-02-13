import logging
import asyncio
from typing import Dict, Type, Optional, Any, Tuple
from enum import Enum, auto

from db_managers import db_manager
from event_bus import event_bus, EventTypes

from models.base import BaseModel
from models.model_lily import ModelLily
from enums import MessageType, MessageTypeCategory, BotStatus

logger = logging.getLogger(__name__)


class ModelInstance:
    def __init__(self, model: BaseModel, message_service: str):
        self.model = model
        self.message_service = message_service


class ModelInstanceStatus(Enum):
    """模型实例状态枚举"""

    AVAILABLE = auto()  # 可用
    SERVICE_MISMATCH = auto()  # 服务不匹配
    NOT_FOUND = auto()  # 未找到实例


class MessageRouter:
    def __init__(self):
        self.model_registry: Dict[str, Type[BaseModel]] = {"lily": ModelLily}
        self.active_models: Dict[str, ModelInstance] = {}
        self.models_lock = asyncio.Lock()

        # 订阅消息事件
        event_bus.subscribe(EventTypes.RECEIVED_MESSAGE, self.handle_received_message)
        event_bus.subscribe(EventTypes.SEND_MESSAGE, self.handle_sent_message)
        logger.info("MessageRouter initialized and subscribed to events")

    def _validate_message(self, message: dict) -> bool:
        """验证消息格式"""
        required_fields = [
            "from_entity",
            "to_entity",
            "message_type",
            "message_service",
        ]
        if not all(field in message for field in required_fields):
            logger.warning(f"Message missing required fields: {message}")
            return False
        return True

    async def save_message(self, message: dict) -> None:
        """保存消息到数据库"""
        try:
            message_type = MessageType.parse(str(message.get("message_type")))
            if message_type and message_type.category == MessageTypeCategory.CONTENT:
                await db_manager.save_message(message)
            else:
                logger.debug(f"Skipping message save for type: {message_type}")
        except Exception as e:
            logger.error(f"Error saving processed message: {str(e)}", exc_info=True)

    async def cleanup_model_instance(self, model_key: str) -> None:
        """清理模型实例的方法
        Args:
            model_key: 模型实例的键
        """
        try:
            async with self.models_lock:
                if model_key in self.active_models:
                    logger.info(f"Cleaning up model instance for bot {model_key}")
                    # 从活动实例字典中移除
                    self.active_models.pop(model_key, None)
                    logger.info(
                        f"Model instance for bot {model_key} cleaned up successfully"
                    )
                else:
                    logger.warning(
                        f"Attempted to clean up non-existent model instance: {model_key}"
                    )

        except Exception as e:
            logger.error(
                f"Error in cleanup_model_instance for {model_key}: {str(e)}",
                exc_info=True,
            )

    async def _verify_user_permission(self, user_entity_id: str, bot: Any) -> bool:
        """验证用户权限"""
        return not bot.user_entity_id or str(bot.user_entity_id) == user_entity_id

    async def _get_and_validate_bot(
        self, bot_entity_id: str, user_entity_id: str
    ) -> Optional[Any]:
        """获取并验证 bot"""
        try:
            bot = await db_manager.get_bot_by_entity_id(bot_entity_id)
            if not bot:
                logger.warning(f"Bot not found by entity_id: {bot_entity_id}")
                return None

            if not await self._verify_user_permission(user_entity_id, bot):
                logger.warning(
                    f"User of entity_id: {user_entity_id} not authorized for bot of entity_id: {bot_entity_id}"
                )
                return None

            if bot.status != BotStatus.ACTIVE:
                logger.info(f"Bot of entity_id: {bot_entity_id} status is {bot.status}")
                return None

            return bot

        except ValueError as e:
            logger.error(
                f"Invalid bot status value for bot of entity_id: {bot_entity_id}: {str(e)}",
                exc_info=True,
            )
            return None
        except Exception as e:
            logger.error(
                f"Error getting/validating bot of entity_id: {str(e)}", exc_info=True
            )
            return None

    async def _create_model_instance(
        self, bot: Any, message_service: str
    ) -> Optional[ModelInstance]:
        """创建新的模型实例

        Args:
            bot: Bot数据库对象
            message_service: 消息服务类型

        Returns:
            Optional[ModelInstance]: 创建的模型实例，如果创建失败则返回None
        """
        try:
            model_key = str(bot.entity_id)

            async with self.models_lock:
                # 创建新实例
                model_class = self.model_registry.get(bot.model)
                if not model_class:
                    logger.error(f"Unsupported model type: {bot.model}")
                    return None

                # 创建模型实例，传入异步清理函数
                model = model_class(
                    bot=bot,
                    message_service=message_service,
                    cleanup_callback=self.cleanup_model_instance,
                )
                model_instance = ModelInstance(model, message_service)
                self.active_models[model_key] = model_instance
                logger.info(f"Created new model instance for bot {model_key}")
                return model_instance

        except Exception as e:
            logger.error(f"Error creating model instance: {str(e)}", exc_info=True)
            return None

    async def _get_active_model_instance(
        self, bot_entity_id: str, message_service: str
    ) -> Tuple[ModelInstanceStatus, Optional[ModelInstance]]:
        """获取活跃的模型实例

        Args:
            bot_entity_id: Bot的实体ID
            message_service: 消息服务类型

        Returns:
            Tuple[ModelInstanceStatus, Optional[ModelInstance]]:
                - 状态枚举值
                - 如果状态为AVAILABLE则返回模型实例，否则返回None
        """
        async with self.models_lock:
            if bot_entity_id in self.active_models:
                instance = self.active_models[bot_entity_id]
                if instance.message_service == message_service:
                    return ModelInstanceStatus.AVAILABLE, instance
                else:
                    logger.debug(
                        f"Message service mismatch for bot {bot_entity_id}: "
                        f"expected {instance.message_service}, got {message_service}"
                    )
                    return ModelInstanceStatus.SERVICE_MISMATCH, None
        return ModelInstanceStatus.NOT_FOUND, None

    async def _route_message(self, message: dict) -> None:
        """路由消息到适当的模型"""
        try:
            bot_entity_id = str(message["to_entity"])
            user_entity_id = str(message["from_entity"])
            message_service = message.get("message_service", "unknown")

            # 首先尝试获取活跃的模型实例
            status, instance = await self._get_active_model_instance(
                bot_entity_id, message_service
            )

            if status == ModelInstanceStatus.AVAILABLE and instance is not None:
                # 如果找到匹配的实例，发送消息
                await instance.model.receive_message(message)
                return
            elif status == ModelInstanceStatus.SERVICE_MISMATCH:
                # 如果服务不匹配，直接返回，不创建新实例
                logger.info(
                    f"Skipping message routing due to service mismatch for bot {bot_entity_id}"
                )
                return

            # 未找到实例，创建新实例并路由消息
            message_type = MessageType.parse(str(message.get("message_type")))
            # 验证消息类型，非内容类消息直接返回
            if not message_type or message_type.category != MessageTypeCategory.CONTENT:
                logger.warning(f"Skipping non-content message routing: {message_type}")
                return

            # 获取并验证 bot
            bot = await self._get_and_validate_bot(bot_entity_id, user_entity_id)
            if not bot:
                return

            # 创建新的模型实例
            model_instance = await self._create_model_instance(bot, message_service)
            if not model_instance:
                return

            # 发送消息给新创建的模型实例
            await model_instance.model.receive_message(message)

        except Exception as e:
            logger.error(f"Error routing message: {str(e)}", exc_info=True)

    async def handle_sent_message(self, message: dict) -> None:
        """处理发送的消息"""
        try:
            # 验证消息必要字段
            if not self._validate_message(message):
                raise ValueError("Invalid sent message format")

            await self.save_message(message)

        except Exception as e:
            logger.error(f"Error saving sent message: {str(e)}", exc_info=True)

    async def handle_received_message(self, message: dict) -> None:
        """处理接收到的消息"""
        try:
            # 验证消息必要字段
            if not self._validate_message(message):
                raise ValueError("Invalid received message format")

            # 验证消息并路由
            asyncio.create_task(self._route_message(message))

            await self.save_message(message)

        except Exception as e:
            logger.error(f"Error processing received message: {str(e)}", exc_info=True)


# 创建全局路由器实例
message_router = MessageRouter()
