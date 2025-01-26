from typing import Dict, Any, Optional
from .base import BaseLLMAPI
import logging

logger = logging.getLogger(__name__)

class MirroredLLMAPI(BaseLLMAPI):
    async def generate_response(self, context: Dict[str, Any]) -> Optional[Dict]:
        """
        直接返回收到的context，用于测试
        Args:
            context: 上下文字典
        Returns:
            Dict: 原样返回收到的context
        """
        logger.info(f"MirroredLLM received context")
        return context

    async def validate_response(self, response: Dict) -> bool:
        """
        验证响应是否存在
        Args:
            response: 响应内容
        Returns:
            bool: 响应是否有效
        """
        return bool(response)