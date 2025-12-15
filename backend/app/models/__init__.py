"""
SQLAlchemy models module.

This module imports all database models to ensure they are registered
with SQLAlchemy's metadata for table creation and migrations.
"""

from .admin import AdminLoginLog, AdminOperationLog, AdminUser
from .ai import (
    AIConversationItem,
    AIConversationItemArchive,
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
from .contact import Contact, ContactRequest
from .discovery import SquareTypeEntry
from .llm import LLMConfig, LLMProvider, LLMTestLog
from .message import MediaFile, MessageDeliveryFailure, MessageHistory
from .profile import Profile, UserProfileLog
from .security import UserRiskStats, UserViolationLog
from .system import (
    StatsAIDaily,
    StatsAIMonthly,
    StatsAIWeekly,
    StatsMessageDaily,
    StatsMessageMonthly,
    StatsMessageWeekly,
    StatsRevenueDaily,
    StatsRevenueMonthly,
    StatsRevenueWeekly,
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
    "LoginRecord",
    "MediaFile",
    "MessageDeliveryFailure",
    "MessageHistory",
    "Profile",
    "SnowflakeModel",
    "SnowflakeQiaoModel",
    "SquareTypeEntry",
    "StatsAIDaily",
    "StatsAIMonthly",
    "StatsAIWeekly",
    "StatsMessageDaily",
    "StatsMessageMonthly",
    "StatsMessageWeekly",
    "StatsRevenueDaily",
    "StatsRevenueMonthly",
    "StatsRevenueWeekly",
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
