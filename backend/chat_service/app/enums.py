import enum
from typing import Set, Optional, Union


class MessageTypeCategory:
    """消息分类"""

    CONTENT = "content"  # 需要保存的内容类消息
    STATUS = "status"  # 状态类消息，不需要保存
    SYSTEM = "system"  # 系统消息


class MessageType(enum.Enum):
    """统一的消息类型定义，用于数据库存储
    value: (数字类型, 字符串类型, 消息分类)
    消息结构:
    接收消息：
        message: 消息字典，包含以下字段：
            - from_entity: str, 发送者ID
            - to_entity: str, 接收者ID
            - content: str, 消息内容，可选
            - message_type: int, 消息类型
            1: chat 聊天消息
            2: typing 开始输入
            3: typing_end 输入结束
            8: chat_notyping 无输入信息的聊天消息
        - message_service: str, 消息服务类型
        - timestamp: str, 时间戳
    发送消息：
        message: 消息字典，包含以下字段：
        - from_entity: str, 发送者ID
        - to_entity: str, 接收者ID
        - content: str, 消息内容，可选
        - message_type: int, 消息类型
            1: chat 聊天消息
            2: typing 输入中消息
            9: system 系统消息
        - message_service: str, 消息服务类型
        - timestamp: str, 时间戳
    """

    # 聊天消息
    CHAT = (1, "chat", MessageTypeCategory.CONTENT)
    CHAT_NOTYPING = (8, "chat_notyping", MessageTypeCategory.CONTENT)

    # 状态消息
    TYPING = (2, "typing", MessageTypeCategory.STATUS)
    TYPING_END = (3, "typing_end", MessageTypeCategory.STATUS)

    # 系统消息
    SYSTEM = (9, "system", MessageTypeCategory.SYSTEM)

    def __init__(self, code: int, name: str, category: str):
        self._code = code
        self._name = name
        self._category = category

    @property
    def code(self) -> int:
        """获取数字类型值"""
        return self._code

    @property
    def name(self) -> str:
        """获取字符串类型值"""
        return self._name

    @property
    def category(self) -> str:
        """获取消息分类"""
        return self._category

    @classmethod
    def from_code(cls, code: int) -> Optional["MessageType"]:
        """通过数字类型获取消息类型"""
        try:
            return next(t for t in cls if t.code == code)
        except StopIteration:
            return None

    @classmethod
    def from_name(cls, name: str) -> Optional["MessageType"]:
        """通过字符串类型获取消息类型"""
        try:
            return next(t for t in cls if t.name == name.lower())
        except StopIteration:
            return None

    @classmethod
    def get_content_types(cls) -> Set[int]:
        """获取所有内容类消息的数字类型值"""
        return {t.code for t in cls if t.category == MessageTypeCategory.CONTENT}

    @classmethod
    def parse(cls, value: Union[int, str]) -> Optional["MessageType"]:
        """解析消息类型
        支持数字和字符串两种输入方式
        """
        if isinstance(value, int):
            return cls.from_code(value)
        elif isinstance(value, str):
            return cls.from_name(value)
        return None


class MessageStatus(enum.Enum):
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class UserStatus(enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BANNED = "banned"


class UserRole(enum.Enum):
    USER = "user"
    ADMIN = "admin"
    TESTER = "tester"


class BotStatus(enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class RelationshipType(enum.Enum):
    STRANGER = "stranger"
    FRIEND = "friend"
    CONFIDANT = "confidant"
    LOVER = "lover"
    EX = "ex"
    NEUTRAL = "neutral"
    DISLIKE = "dislike"
    ENEMY = "enemy"
