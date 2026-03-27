"""System configuration and content enums."""

from enum import IntEnum, StrEnum


class ConfigType(IntEnum):
    """Configuration value type (system_configs.config_type)."""

    STRING = 1
    NUMBER = 2
    BOOLEAN = 3
    JSON = 4
    ENUM = 5  # Select from allowed_values


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


class AlertEventType(StrEnum):
    """Alert event type."""

    MEMORY_REFRESH_MISS_THRESHOLD_EXCEEDED = "MEMORY_REFRESH_MISS_THRESHOLD_EXCEEDED"


class AlertEntityType(StrEnum):
    """Entity types that can be referenced by alert_event_entities."""

    USER = "user"
    AI_INSTANCE = "ai_instance"
