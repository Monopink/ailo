"""SQLAlchemy models module.

This module imports all database models to ensure they are registered
with SQLAlchemy's metadata for table creation and migrations.
"""

from .admin import AdminLoginLog, AdminOperationLog, AdminUser
from .ai import (
    AIConversationItem,
    AIConversationItemArchive,
    AIConversationRuntime,
    AIConversationState,
    AIDimension,
    AIDimensionRelationshipMapping,
    AIInstance,
    AIInstanceDimension,
    AIInstanceMemory,
    AIMessageBuffer,
    AIPersona,
    AIPersonality,
    AIPersonalityPlaceholder,
    AIRelationship,
    AIRequestLog,
    AIStyle,
    AIStyleDimension,
    AITemplate,
    AITemplateMemory,
    AIType,
)
from .backup import BackupJob

# Import base classes first
from .base import (
    AutoIncrementModel,
    Base,
    BaseModel,
    ImmutableAutoIncrementModel,
    ImmutableSnowflakeModel,
    SnowflakeModel,
    SnowflakeQiaoModel,
)
from .campaign import Campaign, CampaignAttribution
from .contact import Contact, ContactRequest
from .content import AppPage, SquareCategory, SquareTypeEntry, SquareUserCategoryState
from .entitlement import (
    EntitlementReasonCode,
    EntitlementType,
    UserEntitlementAccount,
    UserEntitlementLedger,
)
from .growth_reward import GrowthRewardApply, GrowthRewardRule
from .invite import (
    InviteBinding,
    InviteCode,
    InviteEvent,
    InviteIntakeLog,
    InviteRecognitionLog,
)
from .llm import LLMConfig, LLMProvider, LLMTestLog
from .message import (
    MediaFile,
    MessageDelivery,
    MessageDevice,
    MessageDispatchOutbox,
    MessageEndpoint,
    MessageHistory,
)
from .profile import Profile, UserProfileLog
from .redeem import RedeemBatchUserCounter, RedeemCode, RedeemCodeBatch, RedeemCodeClaim
from .security import SecurityIPBlock, SecurityIPRiskStats, UserRiskStats, UserViolationLog
from .system import (
    AlertEvent,
    AlertEventEntity,
    ClientRuntimeObservation,
    StatsAIDaily,
    StatsAIMonthly,
    StatsAIWeekly,
    StatsMessageDaily,
    StatsMessageMonthly,
    StatsMessageWeekly,
    StatsUserDaily,
    StatsUserMonthly,
    StatsUserWeekly,
    SystemConfig,
)

# Import all models to register them with SQLAlchemy
from .user import LoginRecord, User, UserToken

# Export all models for easy importing
__all__ = [
    "AIConversationItem",
    "AIConversationItemArchive",
    "AIConversationRuntime",
    "AIConversationState",
    "AIDimension",
    "AIDimensionRelationshipMapping",
    "AIInstance",
    "AIInstanceDimension",
    "AIInstanceMemory",
    "AIMessageBuffer",
    "AIPersona",
    "AIPersonality",
    "AIPersonalityPlaceholder",
    "AIRelationship",
    "AIRequestLog",
    "AIStyle",
    "AIStyleDimension",
    "AITemplate",
    "AITemplateMemory",
    "AIType",
    "AdminLoginLog",
    "AdminOperationLog",
    "AdminUser",
    "BackupJob",
    "AutoIncrementModel",
    "Base",
    "BaseModel",
    "Contact",
    "ContactRequest",
    "ImmutableAutoIncrementModel",
    "ImmutableSnowflakeModel",
    "LLMConfig",
    "LLMProvider",
    "LLMTestLog",
    "AppPage",
    "SquareCategory",
    "LoginRecord",
    "MediaFile",
    "MessageDevice",
    "MessageEndpoint",
    "MessageDelivery",
    "MessageDispatchOutbox",
    "MessageHistory",
    "Profile",
    "EntitlementReasonCode",
    "EntitlementType",
    "UserEntitlementAccount",
    "UserEntitlementLedger",
    "InviteCode",
    "InviteBinding",
    "InviteEvent",
    "InviteIntakeLog",
    "InviteRecognitionLog",
    "Campaign",
    "CampaignAttribution",
    "RedeemCodeBatch",
    "RedeemBatchUserCounter",
    "RedeemCode",
    "RedeemCodeClaim",
    "GrowthRewardRule",
    "GrowthRewardApply",
    "SnowflakeModel",
    "SnowflakeQiaoModel",
    "SquareTypeEntry",
    "SquareUserCategoryState",
    "StatsAIDaily",
    "StatsAIMonthly",
    "StatsAIWeekly",
    "AlertEvent",
    "AlertEventEntity",
    "ClientRuntimeObservation",
    "StatsMessageDaily",
    "StatsMessageMonthly",
    "StatsMessageWeekly",
    "StatsUserDaily",
    "StatsUserMonthly",
    "StatsUserWeekly",
    "SystemConfig",
    "User",
    "UserProfileLog",
    "SecurityIPBlock",
    "SecurityIPRiskStats",
    "UserRiskStats",
    "UserToken",
    "UserViolationLog",
]
