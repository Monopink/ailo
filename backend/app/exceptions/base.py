"""
Base exception classes.

This module defines the base exception hierarchy and common exception types
used throughout the application.
"""

from typing import Any

from fastapi import status


class BaseAppException(Exception):
    """
    Base exception class for all application exceptions.

    Provides structured error information including error codes,
    HTTP status codes, and additional details.
    """

    def __init__(
        self,
        message: str,
        error_code: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: dict[str, Any] | None = None,
    ):
        """
        Initialize base exception.

        Args:
            message: Human-readable error message
            error_code: Machine-readable error code
            status_code: HTTP status code
            details: Additional error details
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary format."""
        return {
            "error": {"code": self.error_code, "message": self.message, "details": self.details}
        }


class ValidationError(BaseAppException):
    """Exception raised for data validation errors."""

    def __init__(
        self,
        message: str = "Validation failed",
        field: str | None = None,
        value: Any | None = None,
        details: dict[str, Any] | None = None,
    ):
        error_details = details or {}
        if field:
            error_details["field"] = field
        if value is not None:
            error_details["value"] = value

        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=error_details,
        )


class NotFoundError(BaseAppException):
    """Exception raised when a requested resource is not found."""

    def __init__(
        self,
        message: str = "Resource not found",
        resource_type: str | None = None,
        resource_id: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        error_details = details or {}
        if resource_type:
            error_details["resource_type"] = resource_type
        if resource_id:
            error_details["resource_id"] = resource_id

        super().__init__(
            message=message,
            error_code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details=error_details,
        )


class PermissionError(BaseAppException):
    """Exception raised for permission/authorization errors."""

    def __init__(
        self,
        message: str = "Permission denied",
        required_permission: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        error_details = details or {}
        if required_permission:
            error_details["required_permission"] = required_permission

        super().__init__(
            message=message,
            error_code="PERMISSION_DENIED",
            status_code=status.HTTP_403_FORBIDDEN,
            details=error_details,
        )


class ConflictError(BaseAppException):
    """Exception raised for resource conflicts."""

    def __init__(
        self,
        message: str = "Resource conflict",
        conflicting_field: str | None = None,
        conflicting_value: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        error_details = details or {}
        if conflicting_field:
            error_details["conflicting_field"] = conflicting_field
        if conflicting_value:
            error_details["conflicting_value"] = conflicting_value

        super().__init__(
            message=message,
            error_code="CONFLICT",
            status_code=status.HTTP_409_CONFLICT,
            details=error_details,
        )


class ExternalServiceError(BaseAppException):
    """Exception raised for external service errors."""

    def __init__(
        self,
        message: str = "External service error",
        service_name: str | None = None,
        service_error: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        error_details = details or {}
        if service_name:
            error_details["service_name"] = service_name
        if service_error:
            error_details["service_error"] = service_error

        super().__init__(
            message=message,
            error_code="EXTERNAL_SERVICE_ERROR",
            status_code=status.HTTP_502_BAD_GATEWAY,
            details=error_details,
        )


class RateLimitError(BaseAppException):
    """Exception raised when rate limits are exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        limit: int | None = None,
        window: str | None = None,
        retry_after: int | None = None,
        details: dict[str, Any] | None = None,
    ):
        error_details = details or {}
        if limit:
            error_details["limit"] = limit
        if window:
            error_details["window"] = window
        if retry_after:
            error_details["retry_after"] = retry_after

        super().__init__(
            message=message,
            error_code="RATE_LIMIT_EXCEEDED",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details=error_details,
        )


class ConfigurationError(BaseAppException):
    """Exception raised for configuration errors."""

    def __init__(
        self,
        message: str = "Configuration error",
        config_key: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        error_details = details or {}
        if config_key:
            error_details["config_key"] = config_key

        super().__init__(
            message=message,
            error_code="CONFIGURATION_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=error_details,
        )


class MissingConfigurationError(ConfigurationError):
    """Exception raised when a required configuration value is missing."""

    def __init__(self, config_key: str):
        super().__init__(
            message=f"Configuration '{config_key}' is required but not set",
            config_key=config_key,
        )
