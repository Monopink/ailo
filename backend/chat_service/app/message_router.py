import asyncio
import logging
from asyncio import Lock
from datetime import datetime
from typing import Dict, Type, Optional, Callable, Any

from db_managers import db_manager
from event_bus import event_bus, EventTypes

from models.base import BaseModel
from models.model_lily import ModelLily

logger = logging.getLogger(__name__)

class ModelInstance:
    def __init__(self, model: BaseModel, message_service: str):
        self.model = model
        self.message_service = message_service

class MessageRouter:
    def __init__(self):
        self.model_registry: Dict[str, Type[BaseModel]] = {
            'lily': ModelLily
        }
        self.active_models: Dict[str, ModelInstance] = {}
        self.models_lock = Lock()
        
        # 订阅消息事件
        event_bus.subscribe(EventTypes.MESSAGE_RECEIVED, self.handle_message)
        event_bus.subscribe(EventTypes.SEND_MESSAGE, self.save_send_message)
        logger.info("MessageRouter initialized and subscribed to events")

    async def save_send_message(self, message: dict) -> None:
        """保存发送的消息到数据库"""
        try:
            message_type = message.get('message_type')
            if message_type in ['chat', 'system']:
                # 确保消息包含时间戳
                if 'timestamp' not in message:
                    message['timestamp'] = datetime.now()
                
                # 保存接收到的消息
                await db_manager.save_message(message)
            else:
                logger.debug(f"Skipping message save for type: {message_type}")
        except Exception as e:
            logger.error(f"Error saving processed message: {str(e)}", exc_info=True)

    async def cleanup_model(self, model_key: str) -> None:
        """
        清理模型实例的方法
        Args:
            model_key: 模型实例的键
        """
        try:
            async with self.models_lock:
                if model_key in self.active_models:
                    logger.info(f"Cleaning up model instance for bot {model_key}")
                    # 从活动实例字典中移除
                    self.active_models.pop(model_key, None)
                    logger.info(f"Model instance for bot {model_key} cleaned up successfully")
                else:
                    logger.warning(f"Attempted to clean up non-existent model instance: {model_key}")
                
        except Exception as e:
            logger.error(f"Error in cleanup_model for {model_key}: {str(e)}", exc_info=True)

    def _validate_message(self, message: dict) -> bool:
        """验证消息格式"""
        required_fields = ['to_id', 'from_id']
        if not all(field in message for field in required_fields):
            logger.warning(f"Message missing required fields: {message}")
            return False
        return True

    async def _get_and_validate_bot(self, bot_id: str, from_id: str) -> Optional[Any]:
        """获取并验证 bot"""
        try:
            bot = await db_manager.get_bot_by_id(int(bot_id))
            if not bot:
                logger.warning(f"Bot not found: {bot_id}")
                return None

            if not await self._verify_user_permission(from_id, bot):
                logger.warning(f"User {from_id} not authorized for bot {bot_id}")
                return None

            if bot.status.value != 'active':
                logger.info(f"Bot {bot_id} is {bot.status.value}")
                return None

            return bot

        except Exception as e:
            logger.error(f"Error getting/validating bot: {str(e)}", exc_info=True)
            return None

    async def _verify_user_permission(self, user_id: str, bot: Any) -> bool:
        """验证用户权限"""
        return not bot.user_id or str(bot.user_id) == user_id

    async def _get_or_create_model(self, bot: Any, message_service: str) -> Optional[ModelInstance]:
        """获取或创建模型实例"""
        try:
            model_key = str(bot.id)
            
            async with self.models_lock:
                # 检查现有实例
                if model_key in self.active_models:
                    instance = self.active_models[model_key]
                    if instance.message_service != message_service:
                        logger.warning(
                            f"Message service mismatch for bot {bot.id}: "
                            f"expected {instance.message_service}, got {message_service}"
                        )
                        return None
                    return instance

                # 创建新实例
                model_class = self.model_registry.get(bot.model)
                if not model_class:
                    logger.error(f"Unsupported model type: {bot.model}")
                    return None

                # 创建模型实例，传入异步清理函数
                model = model_class(
                    bot=bot,
                    message_service=message_service,
                    cleanup_callback=self.cleanup_model
                )
                self.active_models[model_key] = ModelInstance(model, message_service)
                return self.active_models[model_key]

        except Exception as e:
            logger.error(f"Error getting/creating model instance: {str(e)}", exc_info=True)
            return None

    async def _route_message(self, message: dict) -> None:
        """路由消息到适当的模型"""
        try:
            # 验证消息必要字段
            if not self._validate_message(message):
                return

            bot_id = str(message['to_id'])
            from_id = str(message['from_id'])
            message_service = message.get('message_service', 'unknown')

            # 获取并验证 bot
            bot = await self._get_and_validate_bot(bot_id, from_id)
            if not bot:
                return

            # 获取或创建模型实例
            model_instance = await self._get_or_create_model(bot, message_service)
            if not model_instance:
                return

            # 发送消息给模型实例处理
            await model_instance.model.process_message(message)

        except Exception as e:
            logger.error(f"Error routing message: {str(e)}", exc_info=True)

    async def handle_message(self, message: dict) -> None:
        """处理接收到的消息"""
        try:
            # 确保消息包含时间戳，如果没有则使用当前时间
            if 'timestamp' not in message:
                message['timestamp'] = datetime.now()
            
            await db_manager.save_message(message)
            
            # 验证消息并路由
            await self._route_message(message)
            
        except Exception as e:
            logger.error(f"Error handling message: {str(e)}", exc_info=True)

# 创建全局路由器实例
message_router = MessageRouter()