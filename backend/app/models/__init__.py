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
from .content import AppPage, SquareCategory, SquareTypeEntry
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
from .redeem import RedeemCode, RedeemCodeBatch, RedeemCodeClaim
from .security import UserRiskStats, UserViolationLog
from .system import (
    AlertEvent,
    AlertEventEntity,
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
    "InviteRecognitionLog",
    "Campaign",
    "CampaignAttribution",
    "RedeemCodeBatch",
    "RedeemCode",
    "RedeemCodeClaim",
    "GrowthRewardRule",
    "GrowthRewardApply",
    "SnowflakeModel",
    "SnowflakeQiaoModel",
    "SquareTypeEntry",
    "StatsAIDaily",
    "StatsAIMonthly",
    "StatsAIWeekly",
    "AlertEvent",
    "AlertEventEntity",
    "StatsMessageDaily",
    "StatsMessageMonthly",
    "StatsMessageWeekly",
    "StatsUserDaily",
    "StatsUserMonthly",
    "StatsUserWeekly",
    "SystemConfig",
    "User",
    "UserProfileLog",
    "UserRiskStats",
    "UserToken",
    "UserViolationLog",
]
