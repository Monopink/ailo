"""
AI-related model views for Starlette-Admin.
Creates ModelView instances for AI system models.
"""

from typing import Any, Dict
from starlette.requests import Request
from starlette_admin.contrib.sqla import ModelView
from starlette_admin import EnumField, IntegerField, StringField, TextAreaField
from starlette_admin.actions import link_row_action

# Import AI models
from models.ai.character import AICharacter
from models.ai.personality import AIPersonality, AIPersonalityPlaceholder
from models.ai.style import AIStyle, AIRelationship, AIRelationshipDimension, AIRelationshipIndex
from models.ai.template import AIInfoTemplate, AIProfileTemplate
from models.ai.log import AIRequestLog

# Import enums
from enums import (
    AICharacterCreator,
    AICharacterStatus,
    AIStyleStatus,
    AIRequestStatus,
    ScoreOffsetAlgorithm,
    Gender,
    PlaceholderType,
    RequiredStatus,
    ReusableStatus,
)


class AIPersonalityView(ModelView):
    """Enhanced AI Personality view with proper field configuration."""

    exclude_fields_from_create = ["id", "usage_count", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "usage_count", "created_at", "updated_at"]
    exclude_fields_from_list = ["json_schema", "prompt"]

    def can_delete(self, request: Request) -> bool:
        return False

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["name", "display_name"]
    sortable_fields = ["id", "name", "display_name", "status", "usage_count", "created_at"]

    fields = [
        StringField("id", label="ID", help_text="Internal personality ID"),
        StringField(
            "name",
            label="Personality Name",
            help_text="Unique identifier for the personality",
            required=True,
        ),
        StringField(
            "display_name", label="Display Name", help_text="Human-readable name shown in UI", required=True
        ),
        TextAreaField(
            "prompt",
            label="Personality Prompt",
            help_text="Template for AI personality behavior",
            required=True,
        ),
        "json_schema",
        IntegerField(
            "typing_speed",
            label="Typing Speed (CPM)",
            help_text="Characters per minute typing speed",
            required=True,
        ),
        EnumField(
            "status",
            enum=AIStyleStatus,
            label="Status",
            help_text="Active personalities can be used",
            required=True,
        ),
    ]


class AIPersonalityPlaceholderView(ModelView):
    """Enhanced AI Personality Placeholder view with proper field configuration."""

    exclude_fields_from_create = ["id", "created_at", "updated_at", "validation_rules"]
    exclude_fields_from_edit = ["id", "created_at", "updated_at"]
    exclude_fields_from_list = ["validation_rules", "example_value"]

    def can_delete(self, request: Request) -> bool:
        return False

    fields_default_sort = [("personality_id", False), ("placeholder_key", False)]
    searchable_fields = ["placeholder_key", "display_name"]
    sortable_fields = [
        "id",
        "personality_id",
        "placeholder_key",
        "display_name",
        "placeholder_type",
        "is_required",
    ]

    fields = [
        StringField("id", label="ID", help_text="Internal placeholder ID"),
        IntegerField(
            "personality_id",
            label="Personality ID",
            help_text="AI personality ID this placeholder belongs to",
        ),
        StringField(
            "placeholder_key",
            label="Placeholder Key",
            help_text="Variable name used in prompt template (e.g., {name})",
        ),
        StringField(
            "display_name", label="Display Name", help_text="Human-readable name for this placeholder"
        ),
        StringField(
            "description", label="Description", help_text="Explanation of what this placeholder represents"
        ),
        TextAreaField(
            "example_value",
            label="Example Value",
            help_text="Sample value to help users understand the placeholder",
        ),
        EnumField(
            "placeholder_type",
            enum=PlaceholderType,
            label="Placeholder Type",
            help_text="Data type for validation",
        ),
        EnumField(
            "is_required",
            enum=RequiredStatus,
            label="Required",
            help_text="Whether this placeholder must be filled",
        ),
    ]


class AICharacterView(ModelView):
    """Enhanced AI Character view with proper field configuration and chat test functionality."""

    exclude_fields_from_create = ["id", "qiao_id", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "qiao_id", "created_by", "created_at", "updated_at"]
    exclude_fields_from_list = ["prompt_variables", "memory"]

    def can_delete(self, request: Request) -> bool:
        return False

    async def create(self, request: Request, data: Dict[str, Any]) -> Any:
        """Override create to automatically set created_by field and generate IDs."""
        # Set created_by to 2 (Admin) for admin panel creations
        data["created_by"] = 2

        # Generate qiao_id if not provided
        if not data.get("qiao_id"):
            from models.base import generate_qiao_id

            data["qiao_id"] = generate_qiao_id()

        # Generate id if not provided
        if not data.get("id"):
            from utils.snowflake import generate_snowflake_id

            data["id"] = generate_snowflake_id()

        return await super().create(request, data)

    async def edit(self, request: Request, pk: Any, data: Dict[str, Any]) -> Any:
        """Override edit to handle data processing."""
        return await super().edit(request, pk, data)

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["qiao_id", "category"]
    sortable_fields = ["id", "qiao_id", "category", "status", "created_by", "created_at"]

    fields = [
        StringField("id", label="ID", help_text="Internal character ID"),
        StringField("qiao_id", label="Character ID", help_text="Unique character identifier"),
        StringField("category", label="Category", help_text="Character category classification"),
        IntegerField(
            "user_id",
            label="Owner User ID",
            help_text="User ID who owns this character (optional for system characters)",
        ),
        IntegerField(
            "style_id",
            label="AI Style ID",
            help_text="AI style ID for this character",
            required=True,
        ),
        IntegerField(
            "personality_id",
            label="AI Personality ID",
            help_text="AI personality ID for this character",
            required=True,
        ),
        EnumField(
            "status",
            enum=AICharacterStatus,
            label="Status",
            help_text="Character status: Active characters can be used",
        ),
        TextAreaField(
            "memory",
            label="Memory Settings",
            help_text="Character-specific memory and background information",
        ),
        "prompt_variables",
        IntegerField(
            "score_offset_algorithm",
            label="Score Offset Algorithm",
            help_text="Algorithm for relationship score calculation (1=NONE, 2=V1)",
        ),
        "score_offset_params",
        EnumField(
            "created_by",
            enum=AICharacterCreator,
            label="Created By",
            help_text="Who created this character",
        ),
    ]

    row_actions = ["view", "edit", "chat_test"]

    @link_row_action(
        name="chat_test",
        text="Chat Test",
        icon_class="fas fa-comment-dots",
    )
    def chat_test_row_action(self, request: Request, pk: Any) -> str:
        """Link to AI character chat test page."""
        return f"/qiao-dash/ai-character-chat-test?character_id={pk}"


class AIStyleView(ModelView):
    """Enhanced AI Style view with proper field configuration."""

    exclude_fields_from_create = ["id", "usage_count", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "usage_count", "created_at", "updated_at"]

    def can_delete(self, request):
        return False

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["name", "display_name"]
    sortable_fields = ["id", "name", "display_name", "status", "usage_count", "created_at"]

    fields = [
        StringField("id", label="ID", help_text="Internal style ID"),
        StringField("name", label="Style Name", help_text="Unique identifier for the style", required=True),
        StringField(
            "display_name", label="Display Name", help_text="Human-readable name shown in UI", required=True
        ),
        EnumField(
            "status",
            enum=AIStyleStatus,
            label="Status",
            help_text="Active styles can be used",
            required=True,
        ),
    ]

    row_actions = ["view", "edit", "relationship_management"]

    @link_row_action(
        name="relationship_management",
        text="Relationship Management",
        icon_class="fas fa-chart-line",
    )
    def relationship_management_row_action(self, request: Request, pk: Any) -> str:
        """Link to AI style relationship management page."""
        return f"/qiao-dash/ai-score-algorithm-test?style_id={pk}"


class AIRelationshipView(ModelView):
    """Enhanced AI Relationship view with proper field configuration."""

    exclude_fields_from_create = ["id", "usage_count", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "usage_count", "created_at", "updated_at"]
    exclude_fields_from_list = ["prompt_fragment"]

    def can_delete(self, request):
        return False

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["name", "display_name"]
    sortable_fields = ["id", "name", "display_name", "status", "usage_count", "created_at"]

    fields = [
        StringField("id", label="ID", help_text="Internal relationship ID"),
        StringField(
            "name",
            label="Relationship Name",
            help_text="Unique identifier for the relationship",
            required=True,
        ),
        StringField(
            "display_name", label="Display Name", help_text="Human-readable name shown in UI", required=True
        ),
        TextAreaField(
            "prompt_fragment",
            label="Prompt Fragment",
            help_text="Text fragment to be included in AI prompts for this relationship",
            required=False,
        ),
        EnumField(
            "status",
            enum=AIStyleStatus,
            label="Status",
            help_text="Active relationships can be used",
            required=True,
        ),
    ]


class AIRelationshipDimensionView(ModelView):
    """Enhanced AI Relationship Dimension view with proper field configuration."""

    exclude_fields_from_create = ["id", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "created_at", "updated_at"]

    def can_delete(self, request):
        return False

    fields_default_sort = [("style_id", False), ("name", False)]
    searchable_fields = ["name", "display_name"]
    sortable_fields = ["id", "style_id", "name", "display_name", "initial_position", "created_at"]

    fields = [
        StringField("id", label="ID", help_text="Internal dimension ID"),
        IntegerField(
            "style_id",
            label="AI Style ID",
            help_text="AI style ID this dimension belongs to",
            required=True,
        ),
        StringField(
            "name",
            label="Dimension Name",
            help_text="Internal name used in LLM responses (e.g., 'affection', 'trust')",
            required=True,
        ),
        StringField(
            "display_name", label="Display Name", help_text="Human-readable name shown in UI", required=True
        ),
        IntegerField(
            "initial_position",
            label="Initial Position",
            help_text="Initial position value (0-1000 permille)",
            required=True,
        ),
    ]


class AIRelationshipIndexView(ModelView):
    """Enhanced AI Relationship Index view with position axis visualization."""

    exclude_fields_from_create = ["id", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "created_at", "updated_at"]

    def can_delete(self, request):
        return False

    fields_default_sort = [("style_id", False), ("dimension_name", False), ("start_position", False)]
    searchable_fields = ["dimension_name"]
    sortable_fields = [
        "id",
        "style_id",
        "dimension_name",
        "start_position",
        "end_position",
        "relationship_id",
        "priority",
        "created_at",
    ]

    fields = [
        StringField("id", label="ID", help_text="Internal relationship index ID"),
        IntegerField(
            "style_id",
            label="AI Style ID",
            help_text="AI style ID this index belongs to",
            required=True,
        ),
        IntegerField(
            "dimension_id",
            label="Dimension ID",
            help_text="Relationship dimension ID",
            required=True,
        ),
        StringField(
            "dimension_name",
            label="Dimension Name",
            help_text="Name of the dimension (must match dimension table)",
        ),
        IntegerField(
            "start_position",
            label="Start Position",
            help_text="Start position of the range (0-1000)",
            required=True,
        ),
        IntegerField(
            "end_position",
            label="End Position",
            help_text="End position of the range (0-1000)",
            required=True,
        ),
        IntegerField(
            "relationship_id",
            label="Relationship Type ID",
            help_text="Relationship type ID for this range",
            required=True,
        ),
        IntegerField(
            "priority", label="Priority", help_text="Priority level (lower number = higher priority)"
        ),
        IntegerField(
            "limit_count",
            label="Limit Count",
            help_text="Maximum occurrences (leave empty for unlimited)",
        ),
    ]


class AIInfoTemplateView(ModelView):
    """Enhanced AI Info Template view with proper field configuration."""

    exclude_fields_from_create = ["id", "profile_count", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "profile_count", "created_at", "updated_at"]
    exclude_fields_from_list = ["prompt_variables", "score_offset_params"]

    def can_delete(self, request):
        return False

    fields_default_sort = [("created_at", True)]
    searchable_fields = []
    sortable_fields = ["id", "style_id", "personality_id", "status", "is_reusable", "created_at"]

    fields = [
        StringField("id", label="ID", help_text="Internal info template ID"),
        IntegerField(
            "style_id",
            label="AI Style ID",
            help_text="AI style ID for this template",
        ),
        IntegerField(
            "personality_id",
            label="AI Personality ID",
            help_text="AI personality ID for this template",
        ),
        TextAreaField(
            "memory",
            label="Memory Settings",
            help_text="Default memory settings for characters using this template",
        ),
        "prompt_variables",
        EnumField(
            "score_offset_algorithm",
            enum=ScoreOffsetAlgorithm,
            label="Score Offset Algorithm",
            help_text="Algorithm for relationship score calculation",
        ),
        "score_offset_params",
        EnumField(
            "is_reusable",
            enum=ReusableStatus,
            label="Reusable",
            help_text="Whether this template can be used multiple times",
        ),
        IntegerField(
            "profile_id", label="Profile ID", help_text="Associated profile ID (for single-use templates)"
        ),
        EnumField(
            "status",
            enum=AIStyleStatus,
            label="Status",
            help_text="Active templates can be used",
        ),
    ]


class AIProfileTemplateView(ModelView):
    """Enhanced AI Profile Template view with proper field configuration."""

    exclude_fields_from_create = ["id", "qiao_id", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "qiao_id", "created_at", "updated_at"]

    def can_delete(self, request):
        return False

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["qiao_id", "nickname", "category"]
    sortable_fields = [
        "id",
        "qiao_id",
        "category",
        "nickname",
        "gender",
        "status",
        "is_reusable",
        "created_at",
    ]

    fields = [
        StringField("id", label="ID", help_text="Internal profile template ID"),
        StringField("qiao_id", label="Qiao ID", help_text="External external identifier for this template"),
        StringField("category", label="Category", help_text="Profile template category"),
        IntegerField(
            "info_id",
            label="Info Template ID",
            help_text="Associated AI info template ID",
        ),
        StringField("nickname", label="Nickname", help_text="Character nickname"),
        EnumField("gender", enum=Gender, label="Gender", help_text="Character gender"),
        StringField("avatar_url", label="Avatar URL", help_text="Character avatar image URL"),
        TextAreaField("bio", label="Bio", help_text="Character biography and description"),
        StringField("region", label="Region", help_text="Character location/region"),
        EnumField(
            "is_reusable",
            enum=ReusableStatus,
            label="Reusable",
            help_text="Whether this template can be used multiple times",
        ),
        EnumField(
            "status",
            enum=AIStyleStatus,
            label="Status",
            help_text="Active templates can be used",
        ),
    ]


class AIRequestLogView(ModelView):
    """Enhanced AI Request Log view - read-only for monitoring."""

    exclude_fields_from_create = [
        "id",
        "character_id",
        "user_id",
        "style_id",
        "personality_id",
        "request",
        "response",
        "status",
        "token_count",
        "response_time",
        "created_at",
    ]
    exclude_fields_from_edit = [
        "id",
        "character_id",
        "user_id",
        "style_id",
        "personality_id",
        "request",
        "response",
        "status",
        "token_count",
        "response_time",
        "created_at",
    ]
    exclude_fields_from_list = ["request", "response"]

    def can_create(self, request):
        return False

    def can_edit(self, request):
        return False

    def can_delete(self, request):
        return False

    fields_default_sort = [("created_at", True)]
    searchable_fields = []
    sortable_fields = [
        "id",
        "character_id",
        "user_id",
        "status",
        "token_count",
        "response_time",
        "created_at",
    ]

    fields = [
        StringField("id", label="ID", help_text="Internal request log ID"),
        StringField("character_id", label="AI Character ID", help_text="AI character snowflake ID"),
        StringField("user_id", label="User ID", help_text="User snowflake ID"),
        IntegerField("style_id", label="AI Style ID"),
        IntegerField("personality_id", label="AI Personality ID"),
        EnumField("status", enum=AIRequestStatus, label="Status"),
        IntegerField("token_count", label="Token Count"),
        IntegerField("response_time", label="Response Time (ms)"),
        "created_at",
    ]


# Create view instances
ai_character_view = AICharacterView(
    AICharacter, name="AI Characters", label="Characters", icon="fa fa-robot", identity="ai_character"
)
ai_personality_view = AIPersonalityView(
    AIPersonality,
    name="AI Personalities",
    label="Personalities",
    icon="fa fa-brain",
    identity="ai_personality",
)
ai_personality_placeholder_view = AIPersonalityPlaceholderView(
    AIPersonalityPlaceholder,
    name="AI Personality Placeholders",
    label="Personality Placeholders",
    icon="fa fa-tags",
    identity="ai_personality_placeholder",
)
ai_style_view = AIStyleView(
    AIStyle, name="AI Styles", label="Styles", icon="fa fa-palette", identity="ai_style"
)
ai_relationship_view = AIRelationshipView(
    AIRelationship,
    name="AI Relationships",
    label="Relationships",
    icon="fa fa-heart",
    identity="ai_relationship",
)
ai_relationship_dimension_view = AIRelationshipDimensionView(
    AIRelationshipDimension,
    name="AI Relationship Dimensions",
    label="Relationship Dimensions",
    icon="fa fa-ruler",
    identity="ai_relationship_dimension",
)
ai_relationship_index_view = AIRelationshipIndexView(
    AIRelationshipIndex,
    name="AI Relationship Indexes",
    label="Relationship Indexes",
    icon="fa fa-sitemap",
    identity="ai_relationship_index",
)
ai_info_template_view = AIInfoTemplateView(
    AIInfoTemplate,
    name="AI Info Templates",
    label="Info Templates",
    icon="fa fa-file-text",
    identity="ai_info_template",
)
ai_profile_template_view = AIProfileTemplateView(
    AIProfileTemplate,
    name="AI Profile Templates",
    label="Profile Templates",
    icon="fa fa-file-user",
    identity="ai_profile_template",
)
ai_request_log_view = AIRequestLogView(
    AIRequestLog,
    name="AI Request Logs",
    label="Request Logs",
    icon="fa fa-history",
    identity="ai_request_log",
)

# Export all AI views
AI_MODEL_VIEWS = [
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
]
