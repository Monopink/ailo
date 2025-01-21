from .base import BaseLLMAPI
import logging

logger = logging.getLogger(__name__)

class MirroredLLMAPI(BaseLLMAPI):
    async def generate_response(self, context: dict) -> dict:
        """
        返回用户的输入消息，用于测试
        Args:
            context: 上下文字典
        Returns:
            str: 用户的输入消息
        """
        logger.info(f"MirroredLLM received context")
        return context

    async def validate_response(self, response: str) -> bool:
        """
        验证响应是否存在
        Args:
            response: 响应内容
        Returns:
            bool: 响应是否有效
        """
        return bool(response)