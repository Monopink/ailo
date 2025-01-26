from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class BaseLLMAPI(ABC):
    def __init__(self):
        pass

    @abstractmethod
    async def generate_response(self, context: Dict[str, Any]) -> Optional[Dict]:
        """
        生成响应
        Args:
            context: 包含消息历史、bot信息等的上下文字典
                {
                    "messages": List[Dict],  # 消息历史
                    "bot_name": str,         # bot名称
                    "user_id": str,          # 用户ID
                    "relationship_type": str, # 关系类型
                    "relationship_score": int # 关系分数
                }
        Returns:
            Optional[Dict]: 响应消息
        """
        pass

    @abstractmethod
    async def validate_response(self, response: Dict) -> bool:
        """
        验证响应是否有效
        Args:
            response: 响应内容
        Returns:
            bool: 响应是否有效
        """
        pass
