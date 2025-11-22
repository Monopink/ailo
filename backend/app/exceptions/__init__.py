"""
Custom exceptions module.

This module contains all custom exception classes used throughout the application.
Exceptions are organized by category and provide structured error information.
"""

# Base exceptions
from .base import (
    BaseAppException,
    ValidationError,
    NotFoundError,
    PermissionError,
    ConflictError,
    ExternalServiceError,
    ConfigurationError,
    MissingConfigurationError,
)

# Business exceptions
from .business import (
    UserNotFoundError,
    UserAlreadyExistsError,
    InvalidCredentialsError,
    AccountSuspendedError,
    ContactNotFoundError,
    ContactAlreadyExistsError,
    ContactRequestPendingError,
    ContactRequestInventoryPendingError,
    ContactLimitExceededError,
    MessageDeliveryError,
    MessageTooLongError,
    AIServiceError,
    AIDataAccessError,
    AICharacterNotFoundError,
    AICharacterInactiveError,
    AICharacterCreationError,
    AIConversationError,
    AIRelationshipError,
    SecurityViolationError,
    SnowflakeGeneratorError,
)

# LLM exceptions
from .llm import (
    LLMServiceError,
    LLMEndpointNotFoundError,
    LLMAuthenticationError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMNetworkError,
    LLMConfigurationError,
    LLMNoConfigError,
)

__all__ = [
    # Base exceptions
    "BaseAppException",
    "ValidationError",
    "NotFoundError",
    "PermissionError",
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
    "AICharacterNotFoundError",
    "AICharacterInactiveError",
    "AICharacterCreationError",
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
