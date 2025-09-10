"""
AI system extended admin views.

This module contains Starlette-Admin views for AI contexts and relationship scores.
"""

from typing import Dict, Any
from starlette.requests import Request
from starlette_admin.contrib.sqla import ModelView
from starlette_admin import EnumField, StringField, IntegerField, DateTimeField, TextAreaField
from starlette_admin.exceptions import FormValidationError

# Import AI models
from models.ai import AIContext, AIRelationshipScore

# Import enums
from enums import (
    AIContextRole,
    AIContextSourceType,
)


class AIContextView(ModelView):
    """Enhanced AI Context view for conversation context management."""

    label = "AI Contexts"
    name = "AI Contexts"

    exclude_fields_from_create = ["id", "character_id", "user_id", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "character_id", "user_id", "created_at", "updated_at"]
    exclude_fields_from_list = ["content", "source_message_ids", "context_metadata"]

    # Read-only view for AI contexts (mainly for monitoring)
    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["character_qiao_id", "user_qiao_id"]
    sortable_fields = [
        "id",
        "character_qiao_id",
        "user_qiao_id",
        "role",
        "source_type",
        "position",
        "token_count",
        "reply_status",
        "created_at",
    ]

    fields = [
        StringField("id", label="ID", help_text="Internal context ID"),
        StringField("character_id", label="Character ID", help_text="Character snowflake ID"),
        StringField(
            "character_qiao_id", label="Character Qiao ID", help_text="Character external identifier"
        ),
        StringField("user_id", label="User ID", help_text="User snowflake ID"),
        StringField("user_qiao_id", label="User Qiao ID", help_text="User external identifier"),
        EnumField(
            "role",
            enum=AIContextRole,
            label="Role",
            help_text="Message role in conversation",
        ),
        TextAreaField("content", label="Content", help_text="Message content"),
        EnumField(
            "source_type",
            enum=AIContextSourceType,
            label="Source Type",
            help_text="Source type of the message",
        ),
        "source_message_ids",
        "context_metadata",
        IntegerField("position", label="Position", help_text="Position in conversation sequence"),
        IntegerField("token_count", label="Token Count", help_text="Token count for this message"),
        IntegerField(
            "is_attack",
            label="Is Attack",
            help_text="Whether this is an attack message (1=yes, 0=no)",
        ),
        IntegerField(
            "reply_status",
            label="Reply Status",
            help_text="Reply processing status (1=pending, 2=processing, 3=done)",
        ),
        DateTimeField("created_at", label="Created At", help_text="Context creation time"),
        DateTimeField("updated_at", label="Updated At", help_text="Last update time"),
    ]


class AIRelationshipScoreView(ModelView):
    """Enhanced AI Relationship Score view for relationship scoring management."""

    label = "Relationship Scores"
    name = "Relationship Scores"

    exclude_fields_from_create = ["id", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "character_id", "dimension_id", "created_at", "updated_at"]
    exclude_fields_from_list = ["score_offset_params", "relationship_counts"]

    fields_default_sort = [("score", True)]
    searchable_fields = ["dimension_name", "relationship_display_name"]
    sortable_fields = [
        "id",
        "character_id",
        "dimension_id",
        "dimension_name",
        "score",
        "position",
        "relationship_id",
        "relationship_display_name",
        "created_at",
    ]

    fields = [
        StringField("id", label="ID", help_text="Internal relationship score ID"),
        StringField("character_id", label="Character ID", help_text="Character snowflake ID"),
        IntegerField("dimension_id", label="Dimension ID", help_text="Relationship dimension ID"),
        StringField("dimension_name", label="Dimension Name", help_text="Relationship dimension name"),
        IntegerField("score", label="Score", help_text="Current relationship score (0-1000)"),
        StringField(
            "score_offset_algorithm", label="Score Algorithm", help_text="Score calculation algorithm"
        ),
        "score_offset_params",
        IntegerField("position", label="Position", help_text="Per mille position (0-1000)"),
        IntegerField("relationship_id", label="Relationship ID", help_text="Current relationship type ID"),
        StringField(
            "relationship_display_name",
            label="Relationship Name",
            help_text="Current relationship display name",
        ),
        "relationship_counts",
        DateTimeField("created_at", label="Created At", help_text="Score record creation time"),
        DateTimeField("updated_at", label="Updated At", help_text="Last update time"),
    ]

    async def validate(self, request: Request, data: Dict[str, Any]) -> None:
        """Custom validation for relationship scores."""
        # Validate score range
        if "score" in data:
            score = data["score"]
            if not (0 <= score <= 1000):
                raise FormValidationError({"score": "Score must be between 0 and 1000"})

        # Validate position range
        if "position" in data:
            position = data["position"]
            if not (0 <= position <= 1000):
                raise FormValidationError({"position": "Position must be between 0 and 1000"})

        return await super().validate(request, data)


# Create view instances
ai_context_view = AIContextView(AIContext, name="AI Contexts", icon="fa fa-comments", identity="ai_context")

ai_relationship_score_view = AIRelationshipScoreView(
    AIRelationshipScore, name="Relationship Scores", icon="fa fa-heart", identity="ai_relationship_score"
)

# Export AI extended views
AI_EXTENDED_MODEL_VIEWS = [
    ai_context_view,
    ai_relationship_score_view,
]
