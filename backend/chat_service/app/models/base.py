import logging
import asyncio
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

class BaseModel(ABC):
    def __init__(self, bot: Any, cleanup_callback: Callable[[], None]):
        """
        初始化基础模型
        Args:
            bot: Bot 实例
            cleanup_callback: 清理回调函数
        """
        self.bot = bot
        self.cleanup_callback = cleanup_callback
        
        # 基础属性
        self.is_awake = False
        self.is_processing = False
        self.context: Dict = {}
        self.important_context: Dict = {}
        self.memory: str = ""
        self.relationship_type: str = ""
        self.relationship_score: int = 0
        self.style: str = ""
        
        # 异步相关
        self.message_queue = asyncio.Queue()
        self.processing_lock = asyncio.Lock()
        self.processing_task = None
        self.sleep_task = None

    @abstractmethod
    async def process_message(self, message: dict) -> None:
        """
        处理接收到的消息
        Args:
            message: 消息字典
        """
        pass

    @abstractmethod
    async def generate_response(self, message: dict) -> Optional[dict]:
        """
        生成响应消息
        Args:
            message: 输入消息
        Returns:
            Optional[dict]: 响应消息，如果生成失败则返回 None
        """
        pass

    async def save_context(self) -> None:
        """保存上下文到数据库"""
        try:
            context_data = {
                'bot_id': self.bot.id,
                'context': self.context,
                'important_context': self.important_context,
                'relationship_type': self.relationship_type,
                'relationship_score': self.relationship_score,
                'memory': self.memory
            }
            await db_manager.save_bot_context(context_data)
        except Exception as e:
            logger.error(f"Error saving context: {str(e)}")

    async def load_context(self) -> None:
        """从数据库加载上下文"""
        pass

    async def before_sleep(self) -> None:
        """睡眠前的操作"""
        await self.save_context()

    def update_context(self, key: str, value: Any) -> None:
        """
        更新上下文信息
        Args:
            key: 上下文键
            value: 上下文值
        """
        self.context[key] = value