"""Database enums module.

This module contains all enumeration definitions used in the database.
All enum values correspond to the integer values defined in the database schema.
"""

# Categories: User Management, Contact Management, Message System, Media Files,
# Profile Management, AI System, Security, System Configuration, Admin System,
# and LLM Service.
from .admin import AdminLoginResult, AdminOperationType, AdminRole, AdminStatus
from .ai import (
    AIInstanceCreator,
    AIInstanceMemoryStatus,
    AIInstanceStatus,
    AIMessageBufferState,
    AIPersonalityStatus,
    AIPersonaStatus,
    AIRelationshipStatus,
    AIRequestStatus,
    AIRequestType,
    AIStyleStatus,
    AITemplateStatus,
    BufferMessageCategory,
    ConversationItemContextStatus,
    ConversationItemMessageType,
    ConversationRole,
    LLMRequestStatus,
    MemoryType,
    PositionMappingAlgorithm,
    RequiredStatus,
    ReusableStatus,
)
from .backup import BackupJobStatus
from .campaign import CampaignStatus
from .client import ClientType, LocaleCode
from .contact import (
    AvatarDisplayMode,
    ContactRequestFailureCode,
    ContactRequestRetryFailureCode,
    ContactRequestRetryMode,
    ContactRequestRetryResultStatus,
    ContactRequestRetryRuleCode,
    ContactRequestSource,
    ContactRequestStatus,
    ContactSource,
    ContactType,
)
from .discovery import (
    SQUARE_CATEGORY_THEME_KEY_SET,
    SQUARE_CATEGORY_THEME_KEYS,
    ExposureStrategy,
    SquareCategoryReviewVisibilityScope,
    SquareCategoryStatus,
    SquareCategoryTheme,
    SquareEntryStatus,
    is_valid_square_category_theme,
)
from .entitlement import EntitlementSourceType
from .growth import (
    GrowthRewardRuleStatus,
    GrowthRewardScopeType,
    GrowthRewardTargetRole,
    GrowthRewardTriggerEvent,
)
from .invite import (
    InviteCodeStatus,
    InviteEventType,
    InviteResolveCodeType,
)
from .llm import LLMConfigStatus, LLMErrorCode, LLMTestStatus, ThinkingMode, ToolChoice
from .media import FileStatus, FileType, UploaderType
from .message import (
    ChatInfoType,
    EncryptionType,
    EncryptionVersion,
    MessageDeliveryStatus,
    MessageDirection,
    MessageDispatchOutboxStatus,
    MessageDispatchOutboxType,
    MessageEndpointScope,
    MessageParticipantType,
    MessageTransportProvider,
    MessageType,
    NotificationActionType,
    NotificationStatus,
    NotificationTarget,
    NotificationType,
)
from .profile import Gender, ProfileModifierType, ProfileOwnerType
from .redeem import (
    RedeemCodeBatchStatus,
    RedeemCodeMode,
    RedeemCodeStatus,
)
from .security import (
    AutoAction,
    DetectionSource,
    IPBlockScope,
    IPBlockStatus,
    ManualReviewStatus,
    RiskLevel,
    SeverityLevel,
    ViolationType,
)
from .system import (
    AlertDomain,
    AlertEntityType,
    AlertEventType,
    AlertSeverityLevel,
    AppPageCategory,
    AppPageSourceType,
    AppPageStatus,
    ConfigShape,
    ConfigValueType,
    SystemConfigScope,
)
from .templates import CHAT_INFO_TEMPLATES
from .user import (
    AuthType,
    DeviceType,
    LoginResult,
    LoginType,
    ReviewScope,
    UserAuthStatus,
    UserStatus,
    UserTokenStatus,
    UserType,
)

__all__ = [
    # User Management
    "UserStatus",
    "UserType",
    "ReviewScope",
    "DeviceType",
    "LoginType",
    "AuthType",
    "LoginResult",
    "UserTokenStatus",
    "UserAuthStatus",
    "ClientType",
    "LocaleCode",
    # Contact Management
    "ContactType",
    "ContactSource",
    "AvatarDisplayMode",
    "ContactRequestSource",
    "ContactRequestStatus",
    "ContactRequestFailureCode",
    "ContactRequestRetryFailureCode",
    "ContactRequestRetryMode",
    "ContactRequestRetryResultStatus",
    "ContactRequestRetryRuleCode",
    # Message System
    "MessageDirection",
    "MessageParticipantType",
    "MessageTransportProvider",
    "MessageEndpointScope",
    "BufferMessageCategory",
    "MessageDispatchOutboxType",
    "MessageDispatchOutboxStatus",
    "MessageType",
    "ChatInfoType",
    "NotificationType",
    "NotificationActionType",
    "NotificationTarget",
    "NotificationStatus",
    "MessageDeliveryStatus",
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
    "SQUARE_CATEGORY_THEME_KEYS",
    "SQUARE_CATEGORY_THEME_KEY_SET",
    "is_valid_square_category_theme",
    "SquareCategoryStatus",
    "SquareCategoryReviewVisibilityScope",
    "SquareCategoryTheme",
    "ExposureStrategy",
    "AIInstanceCreator",
    "AIInstanceStatus",
    "AIStyleStatus",
    "AIPersonalityStatus",
    "AIPersonaStatus",
    "AITemplateStatus",
    "AIRelationshipStatus",
    "AIMessageBufferState",
    "ConversationRole",
    "ConversationItemMessageType",
    "ConversationItemContextStatus",
    "MemoryType",
    "AIInstanceMemoryStatus",
    "AIRequestType",
    "AIRequestStatus",
    "PositionMappingAlgorithm",
    "LLMRequestStatus",
    "RequiredStatus",
    "ReusableStatus",
    "SquareEntryStatus",
    "EntitlementSourceType",
    # Invitation
    "InviteCodeStatus",
    "InviteEventType",
    "InviteResolveCodeType",
    "CampaignStatus",
    "GrowthRewardScopeType",
    "GrowthRewardTargetRole",
    "GrowthRewardTriggerEvent",
    "GrowthRewardRuleStatus",
    "RedeemCodeBatchStatus",
    "RedeemCodeMode",
    "RedeemCodeStatus",
    # Security
    "ViolationType",
    "SeverityLevel",
    "AutoAction",
    "ManualReviewStatus",
    "RiskLevel",
    "DetectionSource",
    "IPBlockScope",
    "IPBlockStatus",
    # System Configuration
    "ConfigValueType",
    "ConfigShape",
    "SystemConfigScope",
    "AppPageCategory",
    "AppPageSourceType",
    "AppPageStatus",
    "AlertSeverityLevel",
    "AlertDomain",
    "AlertEventType",
    "AlertEntityType",
    # Admin System
    "AdminRole",
    "AdminStatus",
    "AdminOperationType",
    "AdminLoginResult",
    # Backup
    "BackupJobStatus",
    # LLM Service
    "LLMTestStatus",
    "LLMErrorCode",
    "LLMConfigStatus",
    "ThinkingMode",
    "ToolChoice",
]
