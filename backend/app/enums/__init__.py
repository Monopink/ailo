"""
Database enums module.

This module contains all enumeration definitions used in the database.
All enum values correspond to the integer values defined in the database schema.
"""

from .common import *

__all__ = [
    # User Management
    "UserStatus",
    "UserType",
    "DeviceType",
    "LoginType",
    "LoginResult",
    # Contact Management
    "ContactType",
    "ContactRequestSource",
    "ContactRequestStatus",
    # Message System
    "MessageDirection",
    "MessageParticipantType",
    "ServiceProvider",
    "MessageType",
    "MessageStatus",
    # Media Files
    "FileType",
    "FileStatus",
    "UploaderType",
    # Profile Management
    "Gender",
    "ProfileOwnerType",
    "ProfileModifierType",
    # Emoticons
    "EmoticonCategory",
    "EmoticonCreatorType",
    # AI System
    "AICharacterCreator",
    "AICharacterStatus",
    "AIStyleStatus",
    "AIContextRole",
    "AIContextSourceType",
    "AIRequestStatus",
    "ScoreOffsetAlgorithm",
    # Security
    "ViolationType",
    "SeverityLevel",
    "AutoAction",
    "ManualReviewStatus",
    "RiskLevel",
    # System Configuration
    "ConfigType",
    # Admin System
    "AdminRole",
    "AdminStatus",
    "AdminOperationType",
    "AdminLoginResult",
]
