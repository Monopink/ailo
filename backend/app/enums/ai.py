"""AI system enums."""

from enum import IntEnum, StrEnum


class AITemplateStatus(IntEnum):
    """AI template status (ai_templates.status)."""

    ACTIVE = 1
    INACTIVE = 2
    USED = 3


class AIInstanceStatus(IntEnum):
    """AI instance status (ai_instances.status)."""

    ACTIVE = 1
    INACTIVE = 2
    BLOCKED = 3


class AIStyleStatus(IntEnum):
    """AI style status (ai_styles.status)."""

    ACTIVE = 1
    INACTIVE = 2


class AIPersonaStatus(IntEnum):
    """AI persona status (ai_personas.status)."""

    ACTIVE = 1
    INACTIVE = 2
    USED = 3


class AIPersonalityStatus(IntEnum):
    """AI personality status (ai_personalities.status)."""

    ACTIVE = 1
    INACTIVE = 2


class AIRelationshipStatus(IntEnum):
    """AI relationship status (ai_relationships.status)."""

    ACTIVE = 1
    INACTIVE = 2


class AIMessageBufferState(IntEnum):
    """Message buffer aggregate state (ai_message_buffer.aggregate_state)."""

    WAITING_WAKEUP = 0  # Waiting to finish wake timer before aggregation
    OPEN = 1  # Waiting for merge/timer
    LOCKED = 2  # Processing (only one per conversation)
    COMPLETE = 3  # Processing completed
    CANCELLED = 4  # Preempted by new window or explicitly terminated


class BufferMessageCategory(StrEnum):
    """Persisted buffer message category (ai_message_buffer.last_message_category)."""

    CONTENT_TYPING = "content_typing"
    CONTENT_NO_TYPING = "content_no_typing"
    TYPING_START = "typing_start"
    TYPING_END = "typing_end"


class ConversationItemMessageType(StrEnum):
    """Conversation item message type (ai_conversation_items.message_type)."""

    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"


class AIInstanceCreator(IntEnum):
    """AI instance creator type (ai_instances.created_by)."""

    USER = 1
    ADMIN = 2
    SYSTEM = 3


class ConversationRole(StrEnum):
    """Conversation role type (ai_conversation_items.role)."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class ConversationItemContextStatus(IntEnum):
    """Context inclusion status (ai_conversation_items.is_excluded_from_context)."""

    INCLUDED = 0  # Included in LLM context
    EXCLUDED = 1  # Excluded from LLM context (prompt injection, etc.)


class AIRequestType(StrEnum):
    """AI request type (ai_request_logs.request_type)."""

    PRODUCTION = "production"
    TEST = "test"


class AIRequestStatus(IntEnum):
    """AI request status (ai_request_logs.status)."""

    SUCCESS = 1
    FAILED = 2
    TIMEOUT = 3


class MemoryType(StrEnum):
    """Memory type (ai_template_memories.memory_type, ai_instance_memories.memory_type)."""

    CORE = "core"
    RECENT = "recent"


class AIInstanceMemoryStatus(IntEnum):
    """AI instance memory status (ai_instance_memories.status)."""

    ACTIVE = 1
    ARCHIVED = 2


class PositionMappingAlgorithm(IntEnum):
    """Position mapping algorithm type (ai_instance_dimensions.position_mapping_algorithm, etc.).

    Maps LLM output score to final position value with optional offset adjustments.
    """

    NONE = 1  # No algorithm - direct score mapping (直接映射)
    V1 = 2  # Version 1 algorithm


class LLMRequestStatus(IntEnum):
    """LLM request status (llm_request_logs.status)."""

    PENDING = 1
    SUCCESS = 2
    ERROR = 3


class RequiredStatus(IntEnum):
    """Required status for placeholders and fields."""

    OPTIONAL = 0
    REQUIRED = 1


class ReusableStatus(IntEnum):
    """Reusable status for templates."""

    SINGLE_USE = 0
    REUSABLE = 1  # Can be reused
