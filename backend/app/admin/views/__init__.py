"""
Model views aggregator for Starlette-Admin.

This module imports all model views from different categories and provides
a unified interface for the admin panel setup.
"""

# Import views from different modules
from .ai_personality_views import AI_PERSONALITY_VIEWS
from .ai_character_views import AI_CHARACTER_VIEWS
from .ai_style_views import AI_STYLE_VIEWS
from .ai_template_views import AI_TEMPLATE_VIEWS
from .ai_context_views import AI_CONTEXT_VIEWS
from .ai_log_views import AI_LOG_VIEWS
from .user_views import USER_MODEL_VIEWS
from .message_media_views import MESSAGE_MEDIA_MODEL_VIEWS
from .llm_views import LLM_MODEL_VIEWS
from .security_views import SECURITY_MODEL_VIEWS
from .token_views import TOKEN_MODEL_VIEWS
from .stats_views import STATS_MODEL_VIEWS
from .system_views import SYSTEM_MODEL_VIEWS

from .ai_character_chat_test_view import ai_character_chat_test_view
from .ai_style_test_view import ai_style_test_view
from .llm_test_views import llm_config_test_view

# Import individual AI views for backward compatibility
from .ai_personality_views import (
    ai_personality_view,
    ai_personality_placeholder_view,
)

from .ai_character_views import (
    ai_character_view,
    ai_character_dimension_view,
)

from .ai_style_views import (
    ai_style_view,
    ai_dimension_view,
    ai_relationship_view,
    ai_style_dimension_view,
    ai_dimension_relationship_mapping_view,
)

from .ai_template_views import (
    ai_character_template_view,
    ai_profile_template_view,
)

from .ai_context_views import (
    ai_context_view,
    ai_context_archive_view,
)

from .ai_log_views import (
    ai_request_log_view,
)

from .user_views import (
    user_view,
    profile_view,
    user_profile_log_view,
    contact_view,
    contact_request_view,
)

from .message_media_views import (
    message_history_view,
    media_file_view,
    message_delivery_failure_view,
    notification_push_history_view,
    preset_asset_view,
)

from .llm_views import (
    llm_provider_view,
    llm_config_view,
    llm_test_log_view,
)

from .security_views import (
    user_violation_log_view,
    user_risk_stats_view,
)

from .token_views import (
    user_token_view,
    login_record_view,
    user_auth_view,
)

from .system_views import (
    system_config_view,
    admin_user_view,
    admin_operation_log_view,
    admin_login_log_view,
)

from .stats_views import (
    stats_user_daily_view,
    stats_user_weekly_view,
    stats_user_monthly_view,
    stats_revenue_daily_view,
    stats_revenue_weekly_view,
    stats_revenue_monthly_view,
    stats_message_daily_view,
    stats_message_weekly_view,
    stats_message_monthly_view,
    stats_ai_daily_view,
    stats_ai_weekly_view,
    stats_ai_monthly_view,
)

# Combine all AI views
AI_MODEL_VIEWS = [
    *AI_PERSONALITY_VIEWS,
    *AI_CHARACTER_VIEWS,
    *AI_STYLE_VIEWS,
    *AI_TEMPLATE_VIEWS,
    *AI_CONTEXT_VIEWS,
    *AI_LOG_VIEWS,
]

# Combine all model views for easy import
ALL_MODEL_VIEWS = [
    *USER_MODEL_VIEWS,
    *AI_MODEL_VIEWS,
    *MESSAGE_MEDIA_MODEL_VIEWS,
    *LLM_MODEL_VIEWS,
    *SECURITY_MODEL_VIEWS,
    *TOKEN_MODEL_VIEWS,
    *SYSTEM_MODEL_VIEWS,
    *STATS_MODEL_VIEWS,
]

__all__ = [
    # Collections
    "ALL_MODEL_VIEWS",
    "AI_MODEL_VIEWS",
    "AI_PERSONALITY_VIEWS",
    "AI_CHARACTER_VIEWS",
    "AI_STYLE_VIEWS",
    "AI_TEMPLATE_VIEWS",
    "AI_CONTEXT_VIEWS",
    "AI_LOG_VIEWS",
    "USER_MODEL_VIEWS",
    "MESSAGE_MEDIA_MODEL_VIEWS",
    "LLM_MODEL_VIEWS",
    "SECURITY_MODEL_VIEWS",
    "TOKEN_MODEL_VIEWS",
    "SYSTEM_MODEL_VIEWS",
    "STATS_MODEL_VIEWS",
    # Individual AI views
    "ai_personality_view",
    "ai_personality_placeholder_view",
    "ai_character_view",
    "ai_character_dimension_view",
    "ai_style_view",
    "ai_dimension_view",
    "ai_relationship_view",
    "ai_style_dimension_view",
    "ai_dimension_relationship_mapping_view",
    "ai_character_template_view",
    "ai_profile_template_view",
    "ai_context_view",
    "ai_context_archive_view",
    "ai_request_log_view",
    # Individual user/admin views
    "admin_user_view",
    "admin_operation_log_view",
    "admin_login_log_view",
    "user_view",
    "profile_view",
    "user_profile_log_view",
    "contact_view",
    # Individual message/media views
    "message_history_view",
    "media_file_view",
    "preset_asset_view",
    "system_config_view",
    "notification_push_history_view",
    # Individual LLM views
    "llm_provider_view",
    "llm_config_view",
    "llm_test_log_view",
    # Individual security views
    "user_violation_log_view",
    "user_risk_stats_view",
    # Individual token views
    "user_token_view",
    "login_record_view",
    "user_auth_view",
    # Individual business views
    "contact_request_view",
    "message_delivery_failure_view",
    # Individual statistics views
    "stats_user_daily_view",
    "stats_user_weekly_view",
    "stats_user_monthly_view",
    "stats_revenue_daily_view",
    "stats_revenue_weekly_view",
    "stats_revenue_monthly_view",
    "stats_message_daily_view",
    "stats_message_weekly_view",
    "stats_message_monthly_view",
    "stats_ai_daily_view",
    "stats_ai_weekly_view",
    "stats_ai_monthly_view",
    # AI Testing views (for routing only, not in menu)
    "ai_character_chat_test_view",
    "ai_style_test_view",
    # LLM Testing views (for routing only, not in menu)
    "llm_config_test_view",
]
