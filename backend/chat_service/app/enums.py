import enum
from typing import Set, Optional, Union, Dict, Any


class MessageTypeCategory:
    """Message categories"""

    CONTENT = "content"  # Content messages that need to be saved
    STATUS = "status"  # Status messages that don't need to be saved
    SYSTEM = "system"  # System messages


class MessageType(enum.Enum):
    """Unified message type definition for database storage
    value: (numeric type, string type, message category)
    Message structure:
    Received messages:
        message: Message dictionary with the following fields:
            - from_entity: str, sender ID
            - to_entity: str, receiver ID
            - content: str, message content, optional
            - message_type: int, message type
            1: chat - chat message
            2: typing - typing started
            3: typing_end - typing ended
            8: chat_notyping - chat message without typing indicator
        - message_service: str, message service type
        - message_time: str, timestamp
    Sent messages:
        message: Message dictionary with the following fields:
        - from_entity: str, sender ID
        - to_entity: str, receiver ID
        - content: str, message content, optional
        - message_type: int, message type
            1: chat - chat message
            2: typing - typing indicator message
            9: system - system message
        - message_service: str, message service type
        - messsage_time: str, timestamp
    """

    # Chat messages
    CHAT = (1, "chat", MessageTypeCategory.CONTENT)
    CHAT_NOTYPING = (8, "chat_notyping", MessageTypeCategory.CONTENT)

    # Status messages
    TYPING = (2, "typing", MessageTypeCategory.STATUS)
    TYPING_END = (3, "typing_end", MessageTypeCategory.STATUS)

    # System messages
    SYSTEM = (9, "system", MessageTypeCategory.SYSTEM)

    def __init__(self, code: int, name: str, category: str):
        self._code = code
        self._name = name
        self._category = category

    @property
    def code(self) -> int:
        """Get numeric type value"""
        return self._code

    @property
    def name(self) -> str:
        """Get string type value"""
        return self._name

    @property
    def category(self) -> str:
        """Get message category"""
        return self._category

    @classmethod
    def from_code(cls, code: int) -> Optional["MessageType"]:
        """Get message type by numeric code"""
        try:
            return next(t for t in cls if t.code == code)
        except StopIteration:
            return None

    @classmethod
    def from_name(cls, name: str) -> Optional["MessageType"]:
        """Get message type by string name"""
        try:
            return next(t for t in cls if t.name == name.lower())
        except StopIteration:
            return None

    @classmethod
    def get_content_types(cls) -> Set[int]:
        """Get all numeric type values for content messages"""
        return {t.code for t in cls if t.category == MessageTypeCategory.CONTENT}

    @classmethod
    def parse(cls, value: Union[int, str]) -> Optional["MessageType"]:
        """Parse message type
        Supports both numeric and string input formats
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
    """Relationship types"""

    FRIEND = "friend"  # Friend relationship
    ROMANCE = "romance"  # Romantic relationship

    @classmethod
    def from_dict(cls, relationship: Dict[str, Any]) -> Optional["RelationshipType"]:
        """Get relationship type from relationship dictionary"""
        if not relationship or "type" not in relationship:
            return None
        try:
            return cls(relationship["type"])
        except (ValueError, TypeError):
            return None


class FriendLevel(enum.Enum):
    """Friend relationship levels"""

    HOSTILE = "hostile"  # Hostile
    COLD = "cold"  # Cold
    POLITE = "polite"  # Polite
    NEUTRAL = "neutral"  # Neutral
    FRIENDLY = "friendly"  # Friendly
    WARM = "warm"  # Warm/Close

    @classmethod
    def from_dict(cls, relationship: Dict[str, Any]) -> Optional["FriendLevel"]:
        """Get friend relationship level from relationship dictionary"""
        if (
            not relationship
            or "level" not in relationship
            or relationship.get("type") != RelationshipType.FRIEND.value
        ):
            return None
        try:
            return cls(relationship["level"])
        except (ValueError, TypeError):
            return None


class RomanceLevel(enum.Enum):
    """Romance relationship levels"""

    CRUSHING = "crushing"  # Crushing/Infatuation
    INTIMATE = "intimate"  # Intimate
    ROMANTIC = "romantic"  # Romantic

    @classmethod
    def from_dict(cls, relationship: Dict[str, Any]) -> Optional["RomanceLevel"]:
        """Get romance relationship level from relationship dictionary"""
        if (
            not relationship
            or "level" not in relationship
            or relationship.get("type") != RelationshipType.ROMANCE.value
        ):
            return None
        try:
            return cls(relationship["level"])
        except (ValueError, TypeError):
            return None


class EmotionLevel(enum.Enum):
    """Emotion intensity levels"""

    LEVEL1 = 1  # Mild
    LEVEL2 = 2  # Moderate
    LEVEL3 = 3  # Severe


class EmotionType(enum.Enum):
    """Emotion types"""

    ANGER = "anger"
    MOVED = "moved"


class ValidationErrorType(enum.Enum):
    """Validation error types"""

    MISSING_FIELD = enum.auto()  # Missing required field
    INVALID_TYPE = enum.auto()  # Field type error
    INVALID_VALUE = enum.auto()  # Invalid field value
    INVALID_RANGE = enum.auto()  # Field value out of range


class TaskType(enum.Enum):
    """Task types"""

    ATTACK_CHECK = enum.auto()  # Attack detection
    RESPONSE_DECISION = enum.auto()  # Response decision making
    CONTENT_GENERATION = enum.auto()  # Content generation
    EMOTION_SCORING = enum.auto()  # Emotion scoring
    FRIEND_SCORING = enum.auto()  # Friendship score evaluation
    ROMANCE_SCORING = enum.auto()  # Romance score evaluation
    CONVERSATION_SUMMARY = enum.auto()  # Conversation summary
    IS_IMPORTANT_CONVERSATION = enum.auto()  # Conversation importance assessment


class BufferStatus(enum.Enum):
    """Buffer status"""

    NONE = "none"
    LEVEL_UP_BUFFER = "level_up_buffer"
    LEVEL_DOWN_BUFFER = "level_down_buffer"
