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
    AuthType,
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
    EncryptionType,
    EncryptionVersion,
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
    PROFILE_CATEGORY_API_TO_DB,
    PROFILE_CATEGORY_DB_TO_API,
    AICharacterCreator,
    AICharacterStatus,
    AIStyleStatus,
    AIPersonalityStatus,
    AIRelationshipStatus,
    AIMessageBufferState,
    ConversationRole,
    AIRequestStatus,
    PositionMappingAlgorithm,
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
    "AuthType",
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
    "EncryptionType",
    "EncryptionVersion",
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
    "PROFILE_CATEGORY_API_TO_DB",
    "PROFILE_CATEGORY_DB_TO_API",
    "AICharacterCreator",
    "AICharacterStatus",
    "AIStyleStatus",
    "AIPersonalityStatus",
    "AIRelationshipStatus",
    "AIMessageBufferState",
    "ConversationRole",
    "AIRequestStatus",
    "PositionMappingAlgorithm",
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
