"""System configuration and content enums."""

from enum import IntEnum, StrEnum


class ConfigValueType(IntEnum):
    """Configuration value type (system_configs.value_type)."""

    STRING = 1
    NUMBER = 2
    BOOLEAN = 3
    JSON = 4
    ENUM = 5  # Select from allowed_values
    TIME = 6  # RFC3339/ISO8601 datetime string in UTC


class ConfigShape(IntEnum):
    """Configuration payload shape (system_configs.config_shape)."""

    SINGLE = 1
    ARRAY = 2


class SystemConfigScope(StrEnum):
    """Configuration scope (system_configs.config_scope)."""

    SYSTEM = "system"
    SECURITY = "security"
    OPERATION = "operation"


class AppPageCategory(IntEnum):
    """App page category (app_pages.page_category)."""

    POLICY = 1
    INFO = 2


class AppPageSourceType(IntEnum):
    """App page source type (app_pages.source_type)."""

    MARKDOWN = 1
    HTML = 2


class AppPageStatus(IntEnum):
    """App page status (app_pages.status)."""

    ACTIVE = 1
    INACTIVE = 2


class AlertSeverityLevel(IntEnum):
    """Alert severity level aligned with Python logging levels."""

    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


class AlertDomain(StrEnum):
    """Alert domain used for routing and aggregation."""

    AI_MEMORY = "ai_memory"
    AI_CONVERSATION = "ai_conversation"
    MESSAGE_DISPATCH = "message_dispatch"
    MESSAGE_WEBSOCKET = "message_websocket"
    BACKGROUND_WORKER = "background_worker"
    SYSTEM_CONFIG = "system_config"
    SECURITY = "security"


class AlertEventType(StrEnum):
    """Alert event type."""

    MEMORY_REFRESH_MISS_THRESHOLD_EXCEEDED = "MEMORY_REFRESH_MISS_THRESHOLD_EXCEEDED"
    AI_CONVERSATION_CONTEXT_CONFIG_INVALID = "AI_CONVERSATION_CONTEXT_CONFIG_INVALID"
    AI_CONVERSATION_RETRY_CONFIG_INVALID = "AI_CONVERSATION_RETRY_CONFIG_INVALID"
    AI_CONVERSATION_SYSTEM_FAILURE = "AI_CONVERSATION_SYSTEM_FAILURE"
    MESSAGE_DISPATCH_RETRY_EXHAUSTED = "MESSAGE_DISPATCH_RETRY_EXHAUSTED"
    MESSAGE_DISPATCH_TASK_FAILED = "MESSAGE_DISPATCH_TASK_FAILED"
    MESSAGE_WS_ACTIVE_ENDPOINT_THRESHOLD_EXCEEDED = "MESSAGE_WS_ACTIVE_ENDPOINT_THRESHOLD_EXCEEDED"
    MESSAGE_WS_OUTBOX_BACKLOG_THRESHOLD_EXCEEDED = "MESSAGE_WS_OUTBOX_BACKLOG_THRESHOLD_EXCEEDED"
    MESSAGE_WS_SEND_FAILURE_THRESHOLD_EXCEEDED = "MESSAGE_WS_SEND_FAILURE_THRESHOLD_EXCEEDED"
    MESSAGE_WS_ACK_P95_THRESHOLD_EXCEEDED = "MESSAGE_WS_ACK_P95_THRESHOLD_EXCEEDED"
    MESSAGE_WS_CLIENT_DOMAIN_MISCONFIG_THRESHOLD_EXCEEDED = (
        "MESSAGE_WS_CLIENT_DOMAIN_MISCONFIG_THRESHOLD_EXCEEDED"
    )
    BACKGROUND_WORKER_FAILURE = "BACKGROUND_WORKER_FAILURE"


class AlertEntityType(StrEnum):
    """Entity types that can be referenced by alert_event_entities."""

    USER = "user"
    AI_INSTANCE = "ai_instance"
    AI_MESSAGE_BUFFER = "ai_message_buffer"
    MESSAGE_DISPATCH_OUTBOX = "message_dispatch_outbox"
    BACKGROUND_WORKER = "background_worker"
