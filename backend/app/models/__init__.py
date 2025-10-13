"""
SQLAlchemy models module.

This module imports all database models to ensure they are registered
with SQLAlchemy's metadata for table creation and migrations.
"""

# Import base classes first
from .base import (
    Base,
    BaseModel,
    SnowflakeModel,
    AutoIncrementModel,
    SnowflakeQiaoModel,
    ImmutableSnowflakeModel,
    ImmutableAutoIncrementModel,
)

# Import all models to register them with SQLAlchemy
from .user import User, UserSession, LoginRecord
from .contact import Contact, ContactRequest
from .message import MessageHistory, MessageDeliveryFailure, MediaFile
from .profile import Profile, UserProfileLog
from .ai import (
    AIRelationship,
    AIStyle,
    AIRelationshipIndex,
    AIRelationshipDimension,
    AIPersonality,
    AIPersonalityPlaceholder,
    AIInfoTemplate,
    AIProfileTemplate,
    AICharacter,
    AIContext,
    AIRelationshipScore,
    AIRequestLog,
)
from .system import (
    SystemConfig,
    StatsUserDaily,
    StatsUserWeekly,
    StatsUserMonthly,
    StatsRevenueDaily,
    StatsRevenueWeekly,
    StatsRevenueMonthly,
    StatsMessageDaily,
    StatsMessageWeekly,
    StatsMessageMonthly,
    StatsAIDaily,
    StatsAIWeekly,
    StatsAIMonthly,
)
from .admin import AdminUser, AdminOperationLog, AdminLoginLog
from .security import UserSecurityLog, UserSecurityStats
from .llm import LLMProvider, LLMConfig, LLMTestLog

# Export all models for easy importing
__all__ = [
    # Base classes
    "Base",
    "BaseModel",
    "SnowflakeModel",
    "AutoIncrementModel",
    "SnowflakeQiaoModel",
    "ImmutableSnowflakeModel",
    "ImmutableAutoIncrementModel",
    # User management
    "User",
    "UserSession",
    "LoginRecord",
    # Contact management
    "Contact",
    "ContactRequest",
    # Message system
    "MessageHistory",
    "MessageDeliveryFailure",
    "MediaFile",
    # Profile management
    "Profile",
    "UserProfileLog",
    # AI system
    "AIRelationship",
    "AIStyle",
    "AIRelationshipIndex",
    "AIRelationshipDimension",
    "AIPersonality",
    "AIPersonalityPlaceholder",
    "AIInfoTemplate",
    "AIProfileTemplate",
    "AICharacter",
    "AIContext",
    "AIRelationshipScore",
    "AIRequestLog",
    # System configuration and statistics
    "SystemConfig",
    "StatsUserDaily",
    "StatsUserWeekly",
    "StatsUserMonthly",
    "StatsRevenueDaily",
    "StatsRevenueWeekly",
    "StatsRevenueMonthly",
    "StatsMessageDaily",
    "StatsMessageWeekly",
    "StatsMessageMonthly",
    "StatsAIDaily",
    "StatsAIWeekly",
    "StatsAIMonthly",
    # Admin management
    "AdminUser",
    "AdminOperationLog",
    "AdminLoginLog",
    # Security monitoring
    "UserSecurityLog",
    "UserSecurityStats",
    # LLM management
    "LLMProvider",
    "LLMConfig",
    "LLMTestLog",
]
