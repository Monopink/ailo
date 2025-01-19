from typing import Dict, Type
import logging
from models.base import BaseModel
from models.model_lily import LilyModel
from database import DatabaseManager

logger = logging.getLogger(__name__)

class MessageRouter:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.model_registry: Dict[str, Type[BaseModel]] = {
            'lily': LilyModel
        }
        self.active_models: Dict[str, BaseModel] = {}

    async def route_message(self, message: dict) -> dict:
        """
        路由消息到适当的模型进行处理
        """
        try:
            logger.debug(f"Routing message: {message}")  # 添加调试日志
            
            if 'to_id' not in message:
                raise ValueError("Message missing required field: to_id")
            
            # 获取目标bot的信息
            bot_id = int(message['to_id'])
            bot = await self.db_manager.get_bot_by_id(bot_id)
            
            if not bot:
                raise ValueError(f"Bot not found: {bot_id}")

            # 获取对应的模型类
            model_class = self.model_registry.get(bot.model)
            if not model_class:
                raise ValueError(f"Model type not supported: {bot.model}")

            # 获取或创建模型实例
            model_instance = self.active_models.get(str(bot_id))
            if not model_instance:
                model_instance = model_class(bot, self.db_manager)
                self.active_models[str(bot_id)] = model_instance

            # 处理消息
            response = await model_instance.process_message(message)
            return response

        except Exception as e:
            logger.error(f"Error routing message: {str(e)}, message: {message}")  # 添加消息内容到错误日志
            return {
                'from_id': message.get('to_id', 'system'),
                'to_id': message.get('from_id', 'unknown'),
                'content': f"Error processing message: {str(e)}",
                'message_type': 'error'
            }

    async def cleanup_inactive_models(self, timeout_minutes: int = 30):
        """
        清理长时间不活跃的模型实例
        """
        # 实现清理逻辑，根据最后活动时间删除不活跃的模型实例
        pass