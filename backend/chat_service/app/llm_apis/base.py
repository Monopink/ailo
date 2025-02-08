from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class BaseLLM(ABC):
    def __init__(self):
        pass

    @abstractmethod
    async def generate_response(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成响应
        Args:
            context: 包含消息历史、bot信息等的上下文字典
                {
                    "messages": List[Dict],  # 消息历史
                }
        Returns:
            Optional[Dict]: 响应消息
        """
        pass

    @abstractmethod
    async def validate_response(self, response: Dict) -> tuple[bool, Optional[str]]:
        """
        验证响应是否符合标准LLM响应结构
        Args:
            response: LLM响应内容
        Returns:
            tuple[bool, Optional[str]]: (是否有效, 错误信息)
        """
        pass
