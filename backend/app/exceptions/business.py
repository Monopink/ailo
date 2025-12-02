"""
Business logic exception classes.

This module defines specific exceptions for business logic errors
that occur during application operations.
"""

from typing import Any

from fastapi import status as http_status

from .base import BaseAppException, ConflictError, NotFoundError, ValidationError

# User Management Exceptions


class UserNotFoundError(NotFoundError):
    """Exception raised when a user is not found."""

    def __init__(
        self,
        user_id: str | None = None,
        message: str = "User not found",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message, resource_type="user", resource_id=user_id, details=details
        )
        self.error_code = "USER_NOT_FOUND"


class UserAlreadyExistsError(ConflictError):
    """Exception raised when trying to create a user that already exists."""

    def __init__(
        self,
        field: str,
        value: str,
        message: str = "User already exists",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message, conflicting_field=field, conflicting_value=value, details=details
        )
        self.error_code = "USER_ALREADY_EXISTS"


class InvalidCredentialsError(BaseAppException):
    """Exception raised for invalid login credentials."""

    def __init__(self, message: str = "Invalid credentials", details: dict[str, Any] | None = None):
        super().__init__(
            message=message,
            error_code="INVALID_CREDENTIALS",
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            details=details,
        )


class AccountSuspendedError(BaseAppException):
    """Exception raised when trying to access a suspended account."""

    def __init__(
        self,
        user_id: str | None = None,
        message: str = "Account is suspended",
        details: dict[str, Any] | None = None,
    ):
        error_details = details or {}
        if user_id:
            error_details["user_id"] = user_id

        super().__init__(
            message=message,
            error_code="ACCOUNT_SUSPENDED",
            status_code=http_status.HTTP_403_FORBIDDEN,
            details=error_details,
        )


# Contact Management Exceptions


class ContactNotFoundError(NotFoundError):
    """Exception raised when a contact is not found."""

    def __init__(
        self,
        contact_id: str | None = None,
        message: str = "Contact not found",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message, resource_type="contact", resource_id=contact_id, details=details
        )
        self.error_code = "CONTACT_NOT_FOUND"


class ContactAlreadyExistsError(ConflictError):
    """Exception raised when trying to add a contact that already exists."""

    def __init__(
        self,
        user_id: str,
        contact_id: str,
        message: str = "Contact already exists",
        details: dict[str, Any] | None = None,
    ):
        error_details = details or {}
        error_details.update({"user_id": user_id, "contact_id": contact_id})

        super().__init__(message=message, details=error_details)
        self.error_code = "CONTACT_ALREADY_EXISTS"


class ContactRequestPendingError(ConflictError):
    """Exception raised when a similar contact request is still pending."""

    def __init__(
        self,
        user_qiao_id: str,
        contact_qiao_id: str,
        message: str = "Contact request already pending",
        details: dict[str, Any] | None = None,
    ):
        error_details = details or {}
        error_details.update({"user_qiao_id": user_qiao_id, "contact_qiao_id": contact_qiao_id})

        super().__init__(message=message, details=error_details)
        self.error_code = "CONTACT_REQUEST_PENDING"


class ContactRequestInventoryPendingError(BaseAppException):
    """Exception raised when a contact request is waiting for inventory."""

    def __init__(
        self,
        type_id: int | None = None,
        message: str = "Contact request is waiting for template inventory",
        details: dict[str, Any] | None = None,
    ):
        error_details = details or {}
        if type_id is not None:
            error_details["type_id"] = type_id

        super().__init__(
            message=message,
            error_code="CONTACT_REQUEST_WAITING_INVENTORY",
            status_code=http_status.HTTP_409_CONFLICT,
            details=error_details,
        )


class ContactLimitExceededError(BaseAppException):
    """Exception raised when contact limit is exceeded."""

    def __init__(
        self,
        current_count: int,
        limit: int,
        message: str = "Contact limit exceeded",
        details: dict[str, Any] | None = None,
    ):
        error_details = details or {}
        error_details.update({"current_count": current_count, "limit": limit})

        super().__init__(
            message=message,
            error_code="CONTACT_LIMIT_EXCEEDED",
            status_code=http_status.HTTP_400_BAD_REQUEST,
            details=error_details,
        )


# Message System Exceptions


class MessageDeliveryError(BaseAppException):
    """Exception raised when message delivery fails."""

    def __init__(
        self,
        message_id: str | None = None,
        reason: str | None = None,
        message: str = "Message delivery failed",
        details: dict[str, Any] | None = None,
    ):
        error_details = details or {}
        if message_id:
            error_details["message_id"] = message_id
        if reason:
            error_details["reason"] = reason

        super().__init__(
            message=message,
            error_code="MESSAGE_DELIVERY_ERROR",
            status_code=http_status.HTTP_502_BAD_GATEWAY,
            details=error_details,
        )


class MessageTooLongError(ValidationError):
    """Exception raised when message exceeds length limit."""

    def __init__(
        self,
        current_length: int,
        max_length: int,
        message: str = "Message too long",
        details: dict[str, Any] | None = None,
    ):
        error_details = details or {}
        error_details.update({"current_length": current_length, "max_length": max_length})

        super().__init__(message=message, field="content", details=error_details)
        self.error_code = "MESSAGE_TOO_LONG"


# AI System Exceptions


class AIServiceError(BaseAppException):
    """Exception raised for AI service errors."""

    def __init__(
        self,
        ai_service: str | None = None,
        reason: str | None = None,
        message: str = "AI service error",
        details: dict[str, Any] | None = None,
    ):
        error_details = details or {}
        if ai_service:
            error_details["ai_service"] = ai_service
        if reason:
            error_details["reason"] = reason

        super().__init__(
            message=message,
            error_code="AI_SERVICE_ERROR",
            status_code=http_status.HTTP_502_BAD_GATEWAY,
            details=error_details,
        )


class AIDataAccessError(AIServiceError):
    """Exception raised when AI instance data queries fail."""

    def __init__(
        self,
        query: str | None = None,
        reason: str | None = None,
        message: str = "AI data access failed",
        details: dict[str, Any] | None = None,
    ):
        error_details = details or {}
        if query:
            error_details["query"] = query

        super().__init__(
            ai_service="instance_data",
            reason=reason,
            message=message,
            details=error_details,
        )
        self.error_code = "AI_DATA_ACCESS_ERROR"


class AIInstanceNotFoundError(NotFoundError):
    """Exception raised when an AI instance is not found."""

    def __init__(
        self,
        instance_id: str | None = None,
        message: str = "AI instance not found",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message, resource_type="ai_instance", resource_id=instance_id, details=details
        )
        self.error_code = "AI_INSTANCE_NOT_FOUND"


class AIInstanceInactiveError(BaseAppException):
    """Exception raised when an AI instance is inactive or blocked."""

    def __init__(
        self,
        instance_id: str | None = None,
        status: int | None = None,
        message: str = "AI instance is inactive",
        details: dict[str, Any] | None = None,
    ):
        error_details = details or {}
        if instance_id:
            error_details["instance_id"] = instance_id
        if status:
            error_details["status"] = status

        super().__init__(
            message=message,
            error_code="AI_INSTANCE_INACTIVE",
            status_code=http_status.HTTP_403_FORBIDDEN,
            details=error_details,
        )


class AIConversationError(AIServiceError):
    """Exception raised for conversation processing errors."""

    def __init__(
        self,
        conversation_step: str | None = None,
        reason: str | None = None,
        message: str = "Conversation processing failed",
        details: dict[str, Any] | None = None,
    ):
        error_details = details or {}
        if conversation_step:
            error_details["conversation_step"] = conversation_step

        super().__init__(
            ai_service="conversation",
            reason=reason,
            message=message,
            details=error_details,
        )
        self.error_code = "AI_CONVERSATION_ERROR"


class AIRelationshipError(AIServiceError):
    """Exception raised for relationship scoring errors."""

    def __init__(
        self,
        operation: str | None = None,
        reason: str | None = None,
        message: str = "Relationship operation failed",
        details: dict[str, Any] | None = None,
    ):
        error_details = details or {}
        if operation:
            error_details["operation"] = operation

        super().__init__(
            ai_service="relationship",
            reason=reason,
            message=message,
            details=error_details,
        )
        self.error_code = "AI_RELATIONSHIP_ERROR"


class AIInstanceCreationError(AIServiceError):
    """Exception raised for instance creation errors."""

    def __init__(
        self,
        template_id: str | None = None,
        reason: str | None = None,
        message: str = "Instance creation failed",
        details: dict[str, Any] | None = None,
    ):
        error_details = details or {}
        if template_id:
            error_details["template_id"] = template_id

        super().__init__(
            ai_service="instance_creation",
            reason=reason,
            message=message,
            details=error_details,
        )
        self.error_code = "AI_INSTANCE_CREATION_ERROR"


# Security Exceptions


class SecurityViolationError(BaseAppException):
    """Exception raised for security violations."""

    def __init__(
        self,
        violation_type: str | None = None,
        severity: str | None = None,
        message: str = "Security violation detected",
        details: dict[str, Any] | None = None,
    ):
        error_details = details or {}
        if violation_type:
            error_details["violation_type"] = violation_type
        if severity:
            error_details["severity"] = severity

        super().__init__(
            message=message,
            error_code="SECURITY_VIOLATION",
            status_code=http_status.HTTP_400_BAD_REQUEST,
            details=error_details,
        )


# System Exceptions


class SnowflakeGeneratorError(BaseAppException):
    """Exception raised for Snowflake ID generator errors."""

    def __init__(
        self,
        reason: str | None = None,
        message: str = "Snowflake ID generation failed",
        details: dict[str, Any] | None = None,
    ):
        error_details = details or {}
        if reason:
            error_details["reason"] = reason

        super().__init__(
            message=message,
            error_code="SNOWFLAKE_GENERATOR_ERROR",
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=error_details,
        )
