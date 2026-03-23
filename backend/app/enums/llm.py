"""LLM service enums."""

from enum import IntEnum, StrEnum


class LLMTestStatus(IntEnum):
    """LLM test execution status (llm_test_logs.status)."""

    SUCCESS = 1
    FAILED = 2
    TIMEOUT = 3


class LLMErrorCode(IntEnum):
    """LLM error code classification."""

    UNKNOWN = 0  # Unknown error
    ENDPOINT_NOT_FOUND = 1  # 404: Endpoint not found
    AUTHENTICATION_ERROR = 2  # 401: Invalid API Key
    RATE_LIMIT_EXCEEDED = 3  # 429: Rate limit exceeded
    SERVER_ERROR = 4  # 5xx: Server error
    TIMEOUT = 5  # Request timeout
    NETWORK_ERROR = 6  # Network connection failed
    CONFIGURATION_ERROR = 7  # Configuration error
    NO_CONFIG = 8  # No available configuration


class LLMConfigStatus(IntEnum):
    """LLM configuration status (llm_configs.status)."""

    ACTIVE = 1
    INACTIVE = 2


class ThinkingMode(StrEnum):
    """Thinking mode (llm_configs.thinking_mode)."""

    ENABLED = "enabled"
    DISABLED = "disabled"
    AUTO = "auto"


class ToolChoice(StrEnum):
    """Tool choice behavior (llm_configs.default_tool_choice)."""

    AUTO = "auto"
    NONE = "none"
    REQUIRED = "required"
