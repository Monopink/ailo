from abc import ABC, abstractmethod
from typing import Dict, Any
import asyncio
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class BaseModel(ABC):
    def __init__(self, bot: Any, db_manager: Any):
        self.bot = bot
        self.db_manager = db_manager
        self.context: Dict[str, Any] = {}
        self.session_timeout = timedelta(minutes=30)  # 默认会话超时时间
        self.last_activity = datetime.now()
        self._processing = False
        self._message_buffer = []
        self._wait_task = None
        self.needs_cleanup = False  # 新增清理标志

    @abstractmethod
    async def process_message(self, message: dict) -> dict:
        """
        处理接收到的消息并返回响应
        """
        raise NotImplementedError("Subclasses must implement process_message")

    @abstractmethod
    async def generate_response(self, message: dict) -> dict:
        """
        生成响应消息
        """
        pass

    async def wait_for_completion(self, message: dict, timeout: float = 600) -> dict:
        """等待消息处理完成或超时"""
        try:
            self._message_buffer.append(message)
            if not self._processing:
                self._processing = True
                result = await self._process_buffer(timeout)
                return result or {
                    'from_id': self.bot.id,
                    'to_id': message['from_id'],
                    'content': "无响应",
                    'message_type': 'error'
                }
            result = await self._wait_for_current_processing()
            return result or {
                'from_id': self.bot.id,
                'to_id': message['from_id'],
                'content': "无响应",
                'message_type': 'error'
            }
        except asyncio.TimeoutError:
            return {
                'from_id': self.bot.id,
                'to_id': message['from_id'],
                'content': "会话超时，请重新开始。",
                'message_type': 'timeout'
            }

    async def _process_buffer(self, timeout: float) -> dict | None:
        """
        处理消息缓冲区
        """
        try:
            while self._message_buffer:
                message = self._message_buffer[0]
                response = await self.process_message(message)
                self._message_buffer.pop(0)
                if response:
                    return response
            return None
        finally:
            self._processing = False

    async def _wait_for_current_processing(self) -> dict | None:
        """
        等待当前处理完成
        """
        while self._processing:
            await asyncio.sleep(0.1)
        if self._message_buffer:
            return await self._process_buffer(600)
        return None

    def update_context(self, key: str, value: Any):
        """
        更新上下文信息
        """
        self.context[key] = value
        self.last_activity = datetime.now()

    async def save_context(self):
        """
        保存上下文到数据库
        """
        # 实现保存上下文的逻辑
        pass