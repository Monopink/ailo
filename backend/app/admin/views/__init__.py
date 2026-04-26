"""Model views aggregator for Starlette-Admin.

This module imports all model views from different categories and provides
a unified interface for the admin panel setup.
"""

from .ai_conversation_views import (
    AI_CONVERSATION_VIEWS,
    ai_conversation_item_archive_view,
    ai_conversation_item_view,
    ai_conversation_runtime_view,
    ai_conversation_state_view,
    ai_message_buffer_view,
    ai_message_buffer_wake_event_view,
)
from .ai_instance_views import (
    AI_INSTANCE_VIEWS,
    ai_instance_dimension_view,
    ai_instance_memory_view,
    ai_instance_view,
)
from .ai_log_views import AI_LOG_VIEWS, ai_request_log_view

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
from .ai_template_views import (
    AI_TEMPLATE_VIEWS,
    ai_persona_view,
    ai_template_memory_view,
    ai_template_view,
)
from .ai_type_views import AI_TYPE_VIEWS, ai_type_view
from .backup_views import backup_job_view
from .chat_console_view import chat_console_view
from .content_views import (
    CONTENT_MODEL_VIEWS,
    app_page_view,
    square_category_view,
    square_type_entry_view,
)
from .entitlement_operation_view import entitlement_operation_view
from .entitlement_views import (
    ENTITLEMENT_MODEL_VIEWS,
    entitlement_reason_code_view,
    entitlement_type_view,
    user_entitlement_account_view,
    user_entitlement_ledger_view,
)
from .growth_views import (
    GROWTH_MODEL_VIEWS,
    campaign_attribution_view,
    campaign_view,
    growth_reward_apply_view,
    growth_reward_rule_view,
    invite_binding_view,
    invite_code_view,
    invite_event_view,
    invite_recognition_log_view,
    redeem_code_batch_view,
    redeem_code_claim_view,
    redeem_code_view,
)
from .llm_test_views import llm_config_test_view
from .llm_views import (
    LLM_MODEL_VIEWS,
    llm_config_view,
    llm_provider_view,
    llm_test_log_view,
)
from .message_media_views import (
    MESSAGE_MEDIA_MODEL_VIEWS,
    media_file_view,
    message_delivery_view,
    message_device_view,
    message_dispatch_outbox_view,
    message_endpoint_view,
    message_history_view,
    notification_push_history_view,
)
from .profile_avatar_advanced_edit_view import profile_avatar_advanced_edit_view
from .security_views import (
    SECURITY_MODEL_VIEWS,
    user_risk_stats_view,
    user_violation_log_view,
)
from .stats_views import (
    STATS_MODEL_VIEWS,
    stats_ai_daily_view,
    stats_ai_monthly_view,
    stats_ai_weekly_view,
    stats_message_daily_view,
    stats_message_monthly_view,
    stats_message_weekly_view,
    stats_user_daily_view,
    stats_user_monthly_view,
    stats_user_weekly_view,
)
from .system_views import (
    SYSTEM_MODEL_VIEWS,
    admin_login_log_view,
    admin_operation_log_view,
    admin_user_view,
    alert_event_entity_view,
    alert_event_view,
    system_config_view,
)
from .token_views import (
    TOKEN_MODEL_VIEWS,
    login_record_view,
    user_auth_view,
    user_token_view,
)
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
    *GROWTH_MODEL_VIEWS,
    *ENTITLEMENT_MODEL_VIEWS,
    *SYSTEM_MODEL_VIEWS,
    *STATS_MODEL_VIEWS,
    *CONTENT_MODEL_VIEWS,
]

__all__ = [
    # Collections
    "ALL_MODEL_VIEWS",
    "AI_MODEL_VIEWS",
    "AI_PERSONALITY_VIEWS",
    "AI_INSTANCE_VIEWS",
    "AI_STYLE_VIEWS",
    "AI_TEMPLATE_VIEWS",
    "AI_TYPE_VIEWS",
    "AI_LOG_VIEWS",
    "AI_CONVERSATION_VIEWS",
    "USER_MODEL_VIEWS",
    "MESSAGE_MEDIA_MODEL_VIEWS",
    "LLM_MODEL_VIEWS",
    "SECURITY_MODEL_VIEWS",
    "TOKEN_MODEL_VIEWS",
    "GROWTH_MODEL_VIEWS",
    "ENTITLEMENT_MODEL_VIEWS",
    "SYSTEM_MODEL_VIEWS",
    "STATS_MODEL_VIEWS",
    "CONTENT_MODEL_VIEWS",
    # Individual AI views
    "ai_personality_view",
    "ai_personality_placeholder_view",
    "ai_instance_view",
    "ai_instance_dimension_view",
    "ai_instance_memory_view",
    "ai_style_view",
    "ai_dimension_view",
    "ai_relationship_view",
    "ai_style_dimension_view",
    "ai_dimension_relationship_mapping_view",
    "ai_template_view",
    "ai_template_memory_view",
    "ai_type_view",
    "ai_persona_view",
    "ai_request_log_view",
    "ai_conversation_state_view",
    "ai_conversation_runtime_view",
    "ai_message_buffer_view",
    "ai_message_buffer_wake_event_view",
    "ai_conversation_item_view",
    "ai_conversation_item_archive_view",
    # Individual user/admin views
    "admin_user_view",
    "admin_operation_log_view",
    "admin_login_log_view",
    "alert_event_view",
    "alert_event_entity_view",
    "entitlement_reason_code_view",
    "entitlement_type_view",
    "entitlement_operation_view",
    "app_page_view",
    "user_view",
    "profile_view",
    "user_profile_log_view",
    "contact_view",
    "pending_contact_request_view",
    "profile_avatar_advanced_edit_view",
    # Individual message/media views
    "message_history_view",
    "message_delivery_view",
    "message_dispatch_outbox_view",
    "message_device_view",
    "message_endpoint_view",
    "media_file_view",
    "system_config_view",
    "campaign_view",
    "campaign_attribution_view",
    "growth_reward_apply_view",
    "growth_reward_rule_view",
    "invite_binding_view",
    "invite_code_view",
    "invite_event_view",
    "invite_recognition_log_view",
    "redeem_code_batch_view",
    "redeem_code_view",
    "redeem_code_claim_view",
    "user_entitlement_account_view",
    "user_entitlement_ledger_view",
    "notification_push_history_view",
    "square_category_view",
    "square_type_entry_view",
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
    "contact_request_retry_view",
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
    # Backup views
    "backup_job_view",
    # AI Testing views (for routing only, not in menu)
    "chat_console_view",
    "ai_style_test_view",
    # LLM Testing views (for routing only, not in menu)
    "llm_config_test_view",
]
