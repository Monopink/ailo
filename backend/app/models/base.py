from abc import ABC, abstractmethod
from typing import Dict, Any
import asyncio
from datetime import datetime

class BaseModel(ABC):
    def __init__(self, bot: Any, db_manager: Any):
        self.bot = bot
        self.db_manager = db_manager
        self.context: Dict[str, Any] = {}
        self.last_activity = datetime.now()
        self._processing = False
        self._message_buffer = []
        self._wait_task = None

    @abstractmethod
    async def process_message(self, message: dict) -> dict:
        """
        处理接收到的消息并返回响应
        """
        pass

    @abstractmethod
    async def generate_response(self, message: dict) -> dict:
        """
        生成响应消息
        """
        pass

    async def wait_for_completion(self, message: dict, timeout: float = 600) -> dict:
        """
        等待消息处理完成或超时
        """
        try:
            self._message_buffer.append(message)
            if not self._processing:
                self._processing = True
                return await self._process_buffer(timeout)
            return await self._wait_for_current_processing()
        except asyncio.TimeoutError:
            return {
                'from_id': self.bot.id,
                'to_id': message['from_id'],
                'content': "会话超时，请重新开始。",
                'message_type': 'timeout'
            }

    async def _process_buffer(self, timeout: float) -> dict:
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
        finally:
            self._processing = False

    async def _wait_for_current_processing(self) -> dict:
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