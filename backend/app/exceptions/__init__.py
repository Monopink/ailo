"""Custom exceptions module.

This module contains all custom exception classes used throughout the application.
Exceptions are organized by category and provide structured error information.
"""

# Base exceptions
from .base import (
    BaseAppError,
    ConfigurationError,
    ConflictError,
    ExternalServiceError,
    MissingConfigurationError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)

# Business exceptions
from .business import (
    AccountSuspendedError,
    AIConversationError,
    AIDataAccessError,
    AIInstanceCreationError,
    AIInstanceInactiveError,
    AIInstanceNotFoundError,
    AIRelationshipError,
    AIServiceError,
    ContactAlreadyExistsError,
    ContactLimitExceededError,
    ContactNotFoundError,
    ContactRequestInventoryPendingError,
    ContactRequestPendingError,
    InvalidCredentialsError,
    MessageDeliveryError,
    MessageTooLongError,
    SecurityViolationError,
    SnowflakeGeneratorError,
    UserAlreadyExistsError,
    UserNotFoundError,
)

# LLM exceptions
from .llm import (
    LLMAuthenticationError,
    LLMConfigurationError,
    LLMEndpointNotFoundError,
    LLMNetworkError,
    LLMNoConfigError,
    LLMRateLimitError,
    LLMServiceError,
    LLMTimeoutError,
)

__all__ = [
    # Base exceptions
    "BaseAppError",
    "ValidationError",
    "NotFoundError",
    "PermissionDeniedError",
    "ConflictError",
    "ExternalServiceError",
    "ConfigurationError",
    "MissingConfigurationError",
    # Business exceptions
    "UserNotFoundError",
    "UserAlreadyExistsError",
    "InvalidCredentialsError",
    "AccountSuspendedError",
    "ContactNotFoundError",
    "ContactAlreadyExistsError",
    "ContactRequestPendingError",
    "ContactRequestInventoryPendingError",
    "ContactLimitExceededError",
    "MessageDeliveryError",
    "MessageTooLongError",
    "AIServiceError",
    "AIDataAccessError",
    "AIInstanceNotFoundError",
    "AIInstanceInactiveError",
    "AIInstanceCreationError",
    "AIConversationError",
    "AIRelationshipError",
    "SecurityViolationError",
    "SnowflakeGeneratorError",
    # LLM exceptions
    "LLMServiceError",
    "LLMEndpointNotFoundError",
    "LLMAuthenticationError",
    "LLMRateLimitError",
    "LLMTimeoutError",
    "LLMNetworkError",
    "LLMConfigurationError",
    "LLMNoConfigError",
]
