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
)

# Business exceptions
from .business import (
    UserNotFoundError,
    UserAlreadyExistsError,
    InvalidCredentialsError,
    AccountSuspendedError,
    ContactNotFoundError,
    ContactAlreadyExistsError,
    ContactLimitExceededError,
    MessageDeliveryError,
    MessageTooLongError,
    AIServiceError,
    AICharacterNotFoundError,
    SecurityViolationError,
    SnowflakeGeneratorError,
)

__all__ = [
    # Base exceptions
    "BaseAppException",
    "ValidationError",
    "NotFoundError",
    "PermissionError",
    "ConflictError",
    "ExternalServiceError",
    # Business exceptions
    "UserNotFoundError",
    "UserAlreadyExistsError",
    "InvalidCredentialsError",
    "AccountSuspendedError",
    "ContactNotFoundError",
    "ContactAlreadyExistsError",
    "ContactLimitExceededError",
    "MessageDeliveryError",
    "MessageTooLongError",
    "AIServiceError",
    "AICharacterNotFoundError",
    "SecurityViolationError",
    "SnowflakeGeneratorError",
]
