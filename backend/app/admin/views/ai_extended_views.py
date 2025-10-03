"""
AI system extended admin views.

This module contains Starlette-Admin views for AI contexts and relationship scores.
"""

from typing import Dict, Any
from starlette.requests import Request
from starlette_admin.contrib.sqla import ModelView
from starlette_admin import StringField, IntegerField, DateTimeField, TextAreaField, HasOne
from admin.views.base import IntegerEnumField
from starlette_admin.exceptions import FormValidationError

# Import AI models
from models.ai import AIContext, AIContextArchive, AIRelationshipScore

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
    exclude_fields_from_list = ["source_message_ids", "context_metadata"]

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
        IntegerEnumField(
            "role",
            enum=AIContextRole,
            label="Role",
            help_text="Message role in conversation",
        ),
        TextAreaField("content", label="Content", help_text="Message content"),
        IntegerEnumField(
            "source_type",
            enum=AIContextSourceType,
            label="Source Type",
            help_text="Source type of the message",
        ),
        "source_message_ids",
        "context_metadata",
        IntegerField("position", label="Position", help_text="Position in conversation sequence"),
        IntegerField("token_count", label="Token Count", help_text="Token count for this message"),
        IntegerEnumField(
            "is_attack",
            choices=[(0, "No"), (1, "Yes")],
            label="Is Attack",
            help_text="Whether this is an attack message",
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
    exclude_fields_from_list = ["relationship_counts"]

    def can_delete(self, request: Request) -> bool:
        """Disable delete action for relationship scores."""
        return False

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
        HasOne(
            "character",
            identity="ai_character",
            label="AI Character",
            help_text="AI character",
            required=True,
        ),
        HasOne(
            "dimension",
            identity="ai_relationship_dimension",
            label="Relationship Dimension",
            help_text="Relationship dimension",
            required=True,
        ),
        StringField("dimension_name", label="Dimension Name", help_text="Relationship dimension name"),
        IntegerField("score", label="Score", help_text="Current relationship score (0-1000)"),
        IntegerField("position", label="Position", help_text="Per mille position (0-1000)"),
        HasOne(
            "relationship",
            identity="ai_relationship",
            label="Relationship Type",
            help_text="Current relationship type",
            required=False,
        ),
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
        errors = {}

        # Validate score range (if provided)
        if "score" in data and data["score"] is not None:
            score = data["score"]
            if score < 0 or score > 1000:
                errors["score"] = "Score must be between 0 and 1000"

        # Validate position range (if provided)
        if "position" in data and data["position"] is not None:
            position = data["position"]
            if position < 0 or position > 1000:
                errors["position"] = "Position must be between 0 and 1000"

        if errors:
            raise FormValidationError(errors)

        return await super().validate(request, data)

    async def before_create(self, request: Request, data: Dict[str, Any], obj: Any) -> None:
        """Auto-fill foreign keys and validate uniqueness before creating score."""
        from sqlalchemy import select
        from starlette_admin.exceptions import FormValidationError

        # Auto-fill foreign keys from HasOne relationships
        if hasattr(obj, "character") and obj.character is not None:
            obj.character_id = obj.character.id
        if hasattr(obj, "dimension") and obj.dimension is not None:
            obj.dimension_id = obj.dimension.id
            # Auto-fill dimension_name from dimension object
            if hasattr(obj.dimension, "name"):
                obj.dimension_name = obj.dimension.name
        if hasattr(obj, "relationship") and obj.relationship is not None:
            obj.relationship_id = obj.relationship.id
            # Auto-fill relationship_display_name from relationship object
            if hasattr(obj.relationship, "display_name"):
                obj.relationship_display_name = obj.relationship.display_name

        # Validate required foreign keys
        errors = {}
        if not hasattr(obj, "character_id") or obj.character_id is None:
            errors["character"] = "AI Character is required"
        if not hasattr(obj, "dimension_id") or obj.dimension_id is None:
            errors["dimension"] = "Relationship Dimension is required"

        # Check uniqueness constraint: same character + dimension
        if hasattr(obj, "character_id") and obj.character_id and hasattr(obj, "dimension_name") and obj.dimension_name:
            session = request.state.session
            with session.no_autoflush:
                stmt = select(AIRelationshipScore).where(
                    AIRelationshipScore.character_id == obj.character_id,
                    AIRelationshipScore.dimension_name == obj.dimension_name,
                )
                result = await session.execute(stmt)
                existing_score = result.scalar_one_or_none()
                if existing_score:
                    errors["dimension"] = (
                        f"Relationship score already exists for this character and dimension "
                        f"(ID: {existing_score.id}). Each character can only have one score per dimension."
                    )

        if errors:
            raise FormValidationError(errors)

    async def before_edit(self, request: Request, data: Dict[str, Any], obj: Any) -> None:
        """Auto-fill foreign keys before editing score."""
        from starlette_admin.exceptions import FormValidationError

        # Auto-fill relationship_id and relationship_display_name from HasOne relationship
        if hasattr(obj, "relationship") and obj.relationship is not None:
            obj.relationship_id = obj.relationship.id
            # Auto-fill relationship_display_name from relationship object
            if hasattr(obj.relationship, "display_name"):
                obj.relationship_display_name = obj.relationship.display_name


class AIContextArchiveView(ModelView):
    """AI Context Archive view for viewing archived conversation contexts."""

    label = "Context Archives"
    name = "Context Archives"

    # Read-only view
    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    exclude_fields_from_create = ["id", "character_id", "user_id", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "character_id", "user_id", "created_at", "updated_at"]
    exclude_fields_from_list = ["source_message_ids", "context_metadata"]

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["character_qiao_id", "user_qiao_id"]
    sortable_fields = [
        "id",
        "character_qiao_id",
        "user_qiao_id",
        "role",
        "source_type",
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
        IntegerEnumField(
            "role",
            enum=AIContextRole,
            label="Role",
            help_text="Message role in conversation",
        ),
        TextAreaField("content", label="Content", help_text="Message content"),
        IntegerEnumField(
            "source_type",
            enum=AIContextSourceType,
            label="Source Type",
            help_text="Source type of the message",
        ),
        "source_message_ids",
        "context_metadata",
        IntegerField("token_count", label="Token Count", help_text="Token count for this message"),
        IntegerEnumField(
            "is_attack",
            choices=[(0, "No"), (1, "Yes")],
            label="Is Attack",
            help_text="Whether this is an attack message",
        ),
        IntegerField(
            "reply_status",
            label="Reply Status",
            help_text="Reply processing status (1=pending, 2=processing, 3=done)",
        ),
        DateTimeField("created_at", label="Created At", help_text="Context creation time"),
        DateTimeField("updated_at", label="Updated At", help_text="Last update time"),
    ]


# Create view instances
ai_context_view = AIContextView(AIContext, name="AI Contexts", icon="fa fa-comments", identity="ai_context")

ai_context_archive_view = AIContextArchiveView(
    AIContextArchive, name="Context Archives", icon="fa fa-archive", identity="ai_context_archive"
)

ai_relationship_score_view = AIRelationshipScoreView(
    AIRelationshipScore, name="Relationship Scores", icon="fa fa-heart", identity="ai_relationship_score"
)

# Export AI extended views
AI_EXTENDED_MODEL_VIEWS = [
    ai_context_view,
    ai_context_archive_view,
    ai_relationship_score_view,
]
