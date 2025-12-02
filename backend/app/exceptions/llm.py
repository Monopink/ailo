"""
LLM service exception classes.

This module defines specific exceptions for LLM service errors.
"""

from typing import Any

from fastapi import status as http_status

from .base import ConfigurationError, ExternalServiceError, RateLimitError


class LLMServiceError(ExternalServiceError):
    """Base exception for LLM service errors."""

    def __init__(
        self,
        message: str = "LLM service error",
        provider: str | None = None,
        model: str | None = None,
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        error_details = details or {}
        if provider:
            error_details["provider"] = provider
        if model:
            error_details["model"] = model
        if error_code:
            error_details["error_code"] = error_code

        super().__init__(
            message=message,
            service_name=f"llm_{provider}" if provider else "llm",
            service_error=error_code,
            details=error_details,
        )
        self.error_code = "LLM_SERVICE_ERROR"


class LLMEndpointNotFoundError(LLMServiceError):
    """Exception raised when LLM endpoint/model is not found or inaccessible."""

    def __init__(
        self,
        endpoint: str,
        provider: str | None = None,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        if not message:
            message = f"LLM endpoint not found or not accessible: {endpoint}"

        error_details = details or {}
        error_details["endpoint"] = endpoint

        super().__init__(
            message=message,
            provider=provider,
            model=endpoint,
            error_code="ENDPOINT_NOT_FOUND",
            details=error_details,
        )
        self.error_code = "LLM_ENDPOINT_NOT_FOUND"
        self.status_code = http_status.HTTP_404_NOT_FOUND


class LLMAuthenticationError(LLMServiceError):
    """Exception raised for LLM authentication errors."""

    def __init__(
        self,
        provider: str | None = None,
        message: str = "LLM API key is invalid or expired",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            provider=provider,
            error_code="AUTHENTICATION_ERROR",
            details=details,
        )
        self.error_code = "LLM_AUTHENTICATION_ERROR"
        self.status_code = http_status.HTTP_401_UNAUTHORIZED


class LLMRateLimitError(RateLimitError):
    """Exception raised when LLM rate limit is exceeded."""

    def __init__(
        self,
        provider: str | None = None,
        message: str = "LLM API请求频率超限",
        retry_after: int | None = None,
        details: dict[str, Any] | None = None,
    ):
        error_details = details or {}
        if provider:
            error_details["provider"] = provider

        super().__init__(
            message=message,
            retry_after=retry_after,
            details=error_details,
        )
        self.error_code = "LLM_RATE_LIMIT_EXCEEDED"


class LLMTimeoutError(LLMServiceError):
    """Exception raised when LLM request times out."""

    def __init__(
        self,
        timeout_seconds: int,
        provider: str | None = None,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        if not message:
            message = f"LLM API请求超时 ({timeout_seconds}秒)"

        error_details = details or {}
        error_details["timeout_seconds"] = timeout_seconds

        super().__init__(
            message=message,
            provider=provider,
            error_code="TIMEOUT",
            details=error_details,
        )
        self.error_code = "LLM_TIMEOUT"
        self.status_code = http_status.HTTP_504_GATEWAY_TIMEOUT


class LLMNetworkError(LLMServiceError):
    """Exception raised for LLM network errors."""

    def __init__(
        self,
        provider: str | None = None,
        message: str = "无法连接到LLM API",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            provider=provider,
            error_code="NETWORK_ERROR",
            details=details,
        )
        self.error_code = "LLM_NETWORK_ERROR"
        self.status_code = http_status.HTTP_503_SERVICE_UNAVAILABLE


class LLMConfigurationError(ConfigurationError):
    """Exception raised for LLM configuration errors."""

    def __init__(
        self,
        config_name: str | None = None,
        message: str = "LLM配置错误",
        details: dict[str, Any] | None = None,
    ):
        error_details = details or {}
        if config_name:
            error_details["config_name"] = config_name
        # Do not pass config_key to base class to avoid old naming
        super().__init__(
            message=message,
            details=error_details,
        )
        self.error_code = "LLM_CONFIGURATION_ERROR"


class LLMNoConfigError(LLMConfigurationError):
    """Exception raised when no LLM configuration is available."""

    def __init__(
        self,
        config_name: str | None = None,
        message: str = "没有可用的LLM配置",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            config_name=config_name,
            message=message,
            details=details,
        )
        self.error_code = "LLM_NO_CONFIG"


class LLMRequestError(LLMServiceError):
    """Exception raised for general LLM request errors."""

    def __init__(
        self,
        provider: str | None = None,
        message: str = "LLM请求失败",
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            provider=provider,
            error_code=error_code or "REQUEST_ERROR",
            details=details,
        )
        self.error_code = "LLM_REQUEST_ERROR"
        self.status_code = http_status.HTTP_500_INTERNAL_SERVER_ERROR


class ConfigNotVerifiedError(LLMConfigurationError):
    """Exception raised when LLM config has not been verified for JSON Schema support."""

    def __init__(
        self,
        config_name: str,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        if not message:
            message = (
                f"配置 '{config_name}' 未经过测试验证。"
                f"请先在配置测试页面进行测试，系统会自动检测JSON Schema支持情况。"
            )

        super().__init__(
            config_name=config_name,
            message=message,
            details=details,
        )
        self.error_code = "CONFIG_NOT_VERIFIED"


class JSONSchemaNotSupportedError(LLMConfigurationError):
    """Exception raised when LLM config does not support JSON Schema."""

    def __init__(
        self,
        config_name: str,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        if not message:
            message = (
                f"配置 '{config_name}' 不支持JSON Schema，无法用于AI Instance功能。"
                f"此配置只能用于查看测试响应。"
                f"建议使用其他支持JSON Schema的配置。"
            )

        super().__init__(
            config_name=config_name,
            message=message,
            details=details,
        )
        self.error_code = "JSON_SCHEMA_NOT_SUPPORTED"


class LLMResponseFormatError(LLMServiceError):
    """Exception raised when LLM response format is invalid."""

    def __init__(
        self,
        config_name: str,
        provider: str | None = None,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        if not message:
            message = (
                f"配置 '{config_name}' 返回了非JSON格式的响应。"
                f"配置状态已自动更新为'disabled'。"
                f"请检查endpoint是否发生变化，或使用其他配置。"
            )

        error_details = details or {}
        error_details["config_name"] = config_name

        super().__init__(
            message=message,
            provider=provider,
            error_code="RESPONSE_FORMAT_ERROR",
            details=error_details,
        )
        self.error_code = "LLM_RESPONSE_FORMAT_ERROR"
        self.status_code = http_status.HTTP_500_INTERNAL_SERVER_ERROR
