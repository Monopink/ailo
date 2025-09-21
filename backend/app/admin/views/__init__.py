"""
Model views aggregator for Starlette-Admin.

This module imports all model views from different categories and provides
a unified interface for the admin panel setup.
"""

# Import views from different modules
from .ai_views import AI_MODEL_VIEWS
from .user_admin_views import USER_ADMIN_MODEL_VIEWS
from .message_media_views import MESSAGE_MEDIA_MODEL_VIEWS
from .llm_views import LLM_MODEL_VIEWS
from .security_views import SECURITY_MODEL_VIEWS
from .session_views import SESSION_MODEL_VIEWS
from .business_views import BUSINESS_MODEL_VIEWS
from .ai_extended_views import AI_EXTENDED_MODEL_VIEWS

from .ai_test_views import ai_character_chat_test_view, ai_score_algorithm_test_view, ai_relationship_index_api_view

# Import individual views for backward compatibility
from .ai_views import (
    ai_character_view,
    ai_personality_view,
    ai_personality_placeholder_view,
    ai_style_view,
    ai_relationship_view,
    ai_relationship_dimension_view,
    ai_relationship_index_view,
    ai_info_template_view,
    ai_profile_template_view,
    ai_request_log_view,
)

from .user_admin_views import (
    admin_user_view,
    admin_operation_log_view,
    admin_login_log_view,
    user_view,
    profile_view,
    contact_view,
)

from .message_media_views import (
    message_history_view,
    media_file_view,
    emoticon_view,
    system_config_view,
)

from .llm_views import (
    llm_provider_view,
    llm_config_view,
)

from .security_views import (
    user_security_log_view,
    user_security_stats_view,
)

from .session_views import (
    user_session_view,
    login_record_view,
)

from .business_views import (
    contact_request_view,
    message_delivery_failure_view,
)

from .ai_extended_views import (
    ai_context_view,
    ai_relationship_score_view,
)

# Combine all model views for easy import
ALL_MODEL_VIEWS = [
    *USER_ADMIN_MODEL_VIEWS,
    *AI_MODEL_VIEWS,
    *MESSAGE_MEDIA_MODEL_VIEWS,
    *LLM_MODEL_VIEWS,
    *SECURITY_MODEL_VIEWS,
    *SESSION_MODEL_VIEWS,
    *BUSINESS_MODEL_VIEWS,
    *AI_EXTENDED_MODEL_VIEWS,
]

__all__ = [
    # Collections
    "ALL_MODEL_VIEWS",
    "AI_MODEL_VIEWS",
    "USER_ADMIN_MODEL_VIEWS",
    "MESSAGE_MEDIA_MODEL_VIEWS",
    "LLM_MODEL_VIEWS",
    "SECURITY_MODEL_VIEWS",
    "SESSION_MODEL_VIEWS",
    "BUSINESS_MODEL_VIEWS",
    "AI_EXTENDED_MODEL_VIEWS",
    # Individual AI views
    "ai_character_view",
    "ai_personality_view",
    "ai_personality_placeholder_view",
    "ai_style_view",
    "ai_relationship_view",
    "ai_relationship_dimension_view",
    "ai_relationship_index_view",
    "ai_info_template_view",
    "ai_profile_template_view",
    "ai_request_log_view",
    # Individual user/admin views
    "admin_user_view",
    "admin_operation_log_view",
    "admin_login_log_view",
    "user_view",
    "profile_view",
    "contact_view",
    # Individual message/media views
    "message_history_view",
    "media_file_view",
    "emoticon_view",
    "system_config_view",
    # Individual LLM views
    "llm_provider_view",
    "llm_config_view",
    # Individual security views
    "user_security_log_view",
    "user_security_stats_view",
    # Individual session views
    "user_session_view",
    "login_record_view",
    # Individual business views
    "contact_request_view",
    "message_delivery_failure_view",
    # Individual AI extended views
    "ai_context_view",
    "ai_relationship_score_view",
    # AI Testing views (for routing only, not in menu)
    "ai_character_chat_test_view",
    "ai_score_algorithm_test_view",
    "ai_relationship_index_api_view",
]
