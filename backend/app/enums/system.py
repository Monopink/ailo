"""System configuration and content enums."""

from enum import IntEnum


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
