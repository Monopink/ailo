"""
LLM service exception classes.

This module defines specific exceptions for LLM service errors.
"""

from typing import Any, Dict, Optional
from fastapi import status as http_status
from .base import ExternalServiceError, RateLimitError, ConfigurationError


class LLMServiceError(ExternalServiceError):
    """Base exception for LLM service errors."""

    def __init__(
        self,
        message: str = "LLM service error",
        provider: Optional[str] = None,
        model: Optional[str] = None,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
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
        provider: Optional[str] = None,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        if not message:
            message = f"LLM Endpoint不存在或无权限访问: {endpoint}"

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
        provider: Optional[str] = None,
        message: str = "LLM API Key无效或已过期",
        details: Optional[Dict[str, Any]] = None,
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
        provider: Optional[str] = None,
        message: str = "LLM API请求频率超限",
        retry_after: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
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
        provider: Optional[str] = None,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
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
        provider: Optional[str] = None,
        message: str = "无法连接到LLM API",
        details: Optional[Dict[str, Any]] = None,
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
        config_key: Optional[str] = None,
        message: str = "LLM配置错误",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            config_key=config_key,
            details=details,
        )
        self.error_code = "LLM_CONFIGURATION_ERROR"


class LLMNoConfigError(LLMConfigurationError):
    """Exception raised when no LLM configuration is available."""

    def __init__(
        self,
        config_key: Optional[str] = None,
        message: str = "没有可用的LLM配置",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            config_key=config_key,
            message=message,
            details=details,
        )
        self.error_code = "LLM_NO_CONFIG"
