"""
AI data access layer - focused database operations.

This module provides the data access layer for AI services with clear
separation of concerns across different query types.
"""

# Context and conversation query functions
from .conversation_queries import (
    get_conversation_contexts,
    get_conversation_history,
    get_conversation_item_by_id,
    get_items_for_archiving,
)

# Instance-related query functions
from .instance_queries import (
    get_all_instances,
    get_instance_context,
    get_instance_id_by_qiao_id,
    get_personality_with_placeholders,
    get_style_with_relationships,
    get_user_id_by_qiao_id,
)

# Profile-related query functions
from .profile_queries import get_instance_profile, get_profile_by_owner, get_user_profile

# Relationship scoring query functions
from .relationship_queries import get_instance_relationship_scores, get_relationship_score_ranges

# Complex transactions
from .transactions import create_instance_with_relations, save_ai_request_log

# Database updates (simple operations)
from .updates import (
    create_conversation_item,
    mark_conversation_item_as_excluded,
    update_instance_relationship_scores,
    update_instance_status,
)

__all__ = [
    "create_conversation_item",
    "create_instance_with_relations",
    "get_all_instances",
    "get_conversation_contexts",
    "get_conversation_history",
    "get_conversation_item_by_id",
    "get_instance_context",
    "get_instance_id_by_qiao_id",
    "get_instance_profile",
    "get_instance_relationship_scores",
    "get_items_for_archiving",
    "get_personality_with_placeholders",
    "get_profile_by_owner",
    "get_relationship_score_ranges",
    "get_style_with_relationships",
    "get_user_id_by_qiao_id",
    "get_user_profile",
    "mark_conversation_item_as_excluded",
    "save_ai_request_log",
    "update_instance_relationship_scores",
    "update_instance_status",
]
