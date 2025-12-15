"""
Model views aggregator for Starlette-Admin.

This module imports all model views from different categories and provides
a unified interface for the admin panel setup.
"""

from .ai_conversation_views import (
    AI_CONVERSATION_VIEWS,
    ai_conversation_item_archive_view,
    ai_conversation_item_view,
    ai_conversation_state_view,
    ai_message_buffer_view,
)
from .ai_instance_chat_test_view import ai_instance_chat_test_view
from .ai_instance_views import (
    AI_INSTANCE_VIEWS,
    ai_instance_dimension_view,
    ai_instance_memory_view,
    ai_instance_view,
)
from .ai_log_views import AI_LOG_VIEWS, ai_request_log_view

# Import individual AI views for backward compatibility
# Import views from different modules
from .ai_personality_views import (
    AI_PERSONALITY_VIEWS,
    ai_personality_placeholder_view,
    ai_personality_view,
)
from .ai_style_test_view import ai_style_test_view
from .ai_style_views import (
    AI_STYLE_VIEWS,
    ai_dimension_relationship_mapping_view,
    ai_dimension_view,
    ai_relationship_view,
    ai_style_dimension_view,
    ai_style_view,
)
from .ai_template_views import AI_TEMPLATE_VIEWS, ai_persona_view, ai_template_view
from .ai_type_views import AI_TYPE_VIEWS, ai_type_view
from .discovery_views import DISCOVERY_MODEL_VIEWS, square_type_entry_view
from .llm_test_views import llm_config_test_view
from .llm_views import LLM_MODEL_VIEWS, llm_config_view, llm_provider_view, llm_test_log_view
from .message_media_views import (
    MESSAGE_MEDIA_MODEL_VIEWS,
    media_file_view,
    message_delivery_failure_view,
    message_history_view,
    notification_push_history_view,
    preset_asset_view,
)
from .security_views import SECURITY_MODEL_VIEWS, user_risk_stats_view, user_violation_log_view
from .stats_views import (
    STATS_MODEL_VIEWS,
    stats_ai_daily_view,
    stats_ai_monthly_view,
    stats_ai_weekly_view,
    stats_message_daily_view,
    stats_message_monthly_view,
    stats_message_weekly_view,
    stats_revenue_daily_view,
    stats_revenue_monthly_view,
    stats_revenue_weekly_view,
    stats_user_daily_view,
    stats_user_monthly_view,
    stats_user_weekly_view,
)
from .system_views import (
    SYSTEM_MODEL_VIEWS,
    admin_login_log_view,
    admin_operation_log_view,
    admin_user_view,
    system_config_view,
)
from .token_views import TOKEN_MODEL_VIEWS, login_record_view, user_auth_view, user_token_view
from .user_views import (
    USER_MODEL_VIEWS,
    contact_request_retry_view,
    contact_request_view,
    contact_view,
    pending_contact_request_view,
    profile_view,
    user_profile_log_view,
    user_view,
)

# Combine all AI views
AI_MODEL_VIEWS = [
    *AI_PERSONALITY_VIEWS,
    *AI_INSTANCE_VIEWS,
    *AI_STYLE_VIEWS,
    *AI_TEMPLATE_VIEWS,
    *AI_TYPE_VIEWS,
    *AI_LOG_VIEWS,
    *AI_CONVERSATION_VIEWS,
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
    *DISCOVERY_MODEL_VIEWS,
]

__all__ = [
    "AI_CONVERSATION_VIEWS",
    "AI_INSTANCE_VIEWS",
    "AI_LOG_VIEWS",
    "AI_MODEL_VIEWS",
    "AI_PERSONALITY_VIEWS",
    "AI_STYLE_VIEWS",
    "AI_TEMPLATE_VIEWS",
    "AI_TYPE_VIEWS",
    "ALL_MODEL_VIEWS",
    "DISCOVERY_MODEL_VIEWS",
    "LLM_MODEL_VIEWS",
    "MESSAGE_MEDIA_MODEL_VIEWS",
    "SECURITY_MODEL_VIEWS",
    "STATS_MODEL_VIEWS",
    "SYSTEM_MODEL_VIEWS",
    "TOKEN_MODEL_VIEWS",
    "USER_MODEL_VIEWS",
    "admin_login_log_view",
    "admin_operation_log_view",
    "admin_user_view",
    "ai_conversation_item_archive_view",
    "ai_conversation_item_view",
    "ai_conversation_state_view",
    "ai_dimension_relationship_mapping_view",
    "ai_dimension_view",
    "ai_instance_chat_test_view",
    "ai_instance_dimension_view",
    "ai_instance_memory_view",
    "ai_instance_view",
    "ai_message_buffer_view",
    "ai_persona_view",
    "ai_personality_placeholder_view",
    "ai_personality_view",
    "ai_relationship_view",
    "ai_request_log_view",
    "ai_style_dimension_view",
    "ai_style_test_view",
    "ai_style_view",
    "ai_template_view",
    "ai_type_view",
    "contact_request_retry_view",
    "contact_request_view",
    "contact_view",
    "llm_config_test_view",
    "llm_config_view",
    "llm_provider_view",
    "llm_test_log_view",
    "login_record_view",
    "media_file_view",
    "message_delivery_failure_view",
    "message_history_view",
    "notification_push_history_view",
    "pending_contact_request_view",
    "preset_asset_view",
    "profile_view",
    "square_type_entry_view",
    "stats_ai_daily_view",
    "stats_ai_monthly_view",
    "stats_ai_weekly_view",
    "stats_message_daily_view",
    "stats_message_monthly_view",
    "stats_message_weekly_view",
    "stats_revenue_daily_view",
    "stats_revenue_monthly_view",
    "stats_revenue_weekly_view",
    "stats_user_daily_view",
    "stats_user_monthly_view",
    "stats_user_weekly_view",
    "system_config_view",
    "user_auth_view",
    "user_profile_log_view",
    "user_risk_stats_view",
    "user_token_view",
    "user_view",
    "user_violation_log_view",
]
