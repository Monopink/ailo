"""
Database enums module.

This module contains all enumeration definitions used in the database.
All enum values correspond to the integer values defined in the database schema.
"""

from .common import (
    # User Management
    UserStatus,
    UserType,
    DeviceType,
    LoginType,
    LoginResult,
    # Contact Management
    ContactType,
    ContactRequestSource,
    ContactRequestStatus,
    # Message System
    MessageDirection,
    MessageParticipantType,
    ServiceProvider,
    MessageType,
    ChatInfoType,
    NotificationType,
    NotificationActionType,
    NotificationTarget,
    NotificationStatus,
    MessageStatus,
    # Media Files
    FileType,
    FileStatus,
    UploaderType,
    # Profile Management
    Gender,
    ProfileOwnerType,
    ProfileModifierType,
    # AI System
    AIProfileCategory,
    AICharacterCreator,
    AICharacterStatus,
    AIStyleStatus,
    AIPersonalityStatus,
    AIRelationshipStatus,
    AIContextRole,
    AIContextSourceType,
    AIContextReplyStatus,
    AIRequestStatus,
    ScoreOffsetAlgorithm,
    LLMRequestStatus,
    RequiredStatus,
    ReusableStatus,
    # Security
    ViolationType,
    SeverityLevel,
    AutoAction,
    ManualReviewStatus,
    RiskLevel,
    # System Configuration
    ConfigType,
    # Admin System
    AdminRole,
    AdminStatus,
    AdminOperationType,
    AdminLoginResult,
    # LLM Service
    LLMTestStatus,
    LLMErrorCode,
)

from .templates import CHAT_INFO_TEMPLATES

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
    "ChatInfoType",
    "NotificationType",
    "NotificationActionType",
    "NotificationTarget",
    "NotificationStatus",
    "MessageStatus",
    "CHAT_INFO_TEMPLATES",
    # Media Files
    "FileType",
    "FileStatus",
    "UploaderType",
    # Profile Management
    "Gender",
    "ProfileOwnerType",
    "ProfileModifierType",
    # AI System
    "AIProfileCategory",
    "AICharacterCreator",
    "AICharacterStatus",
    "AIStyleStatus",
    "AIPersonalityStatus",
    "AIRelationshipStatus",
    "AIContextRole",
    "AIContextSourceType",
    "AIContextReplyStatus",
    "AIRequestStatus",
    "ScoreOffsetAlgorithm",
    "LLMRequestStatus",
    "RequiredStatus",
    "ReusableStatus",
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
    # LLM Service
    "LLMTestStatus",
    "LLMErrorCode",
]
