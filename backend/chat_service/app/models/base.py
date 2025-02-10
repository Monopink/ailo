from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional, Awaitable


class BaseModel(ABC):
    """模型基类"""

    def __init__(
        self,
        bot: Any,
        message_service: str,
        cleanup_callback: Callable[[str], Awaitable[None]],
    ):
        """
        初始化模型
        Args:
            bot: Bot 实例，包含 bot 的基本信息
            message_service: 消息服务类型
            cleanup_callback: 清理回调函数，接受一个字符串参数（bot.entity_id）并返回一个可等待对象
        """
        self.bot = bot
        self.message_service = message_service
        self.cleanup_callback = cleanup_callback

    @abstractmethod
    async def receive_message(self, message: Dict[str, Any]) -> None:
        """
        接收消息的入口方法

        Args:
            message: 消息字典，包含以下字段：
                - from_entity: str, 发送者ID
                - to_entity: str, 接收者ID
                - content: str, 消息内容
                - message_type: str, 消息类型
                - message_service: str, 消息服务类型
                - timestamp: str, 时间戳
        """
        pass
