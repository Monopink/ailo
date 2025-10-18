"""
AI-related model views for Starlette-Admin.
Creates ModelView instances for AI system models.
"""

from typing import Any, Dict
from starlette.requests import Request
from starlette_admin.contrib.sqla import ModelView
from starlette_admin import IntegerField, StringField, TextAreaField, HasOne
from starlette_admin.actions import link_row_action
from starlette_admin.fields import JSONField

from models.ai.character import AICharacter
from models.ai.personality import AIPersonality, AIPersonalityPlaceholder
from models.ai.style import AIStyle, AIRelationship, AIRelationshipDimension, AIRelationshipIndex
from models.ai.template import AIInfoTemplate, AIProfileTemplate
from models.ai.log import AIRequestLog
from admin.views.base import IntegerEnumField

from enums import (
    AICharacterCreator,
    AICharacterStatus,
    AIStyleStatus,
    AIPersonalityStatus,
    AIRequestStatus,
    ScoreOffsetAlgorithm,
    Gender,
    RequiredStatus,
    ReusableStatus,
)


class AIPersonalityView(ModelView):
    """Enhanced AI Personality view with proper field configuration."""

    exclude_fields_from_create = ["id", "usage_count", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "usage_count", "created_at", "updated_at"]
    exclude_fields_from_list = ["json_schema", "prompt"]

    row_actions = ["view", "edit", "edit_complete"]

    def can_delete(self, request: Request) -> bool:
        return False

    async def before_edit(self, request: Request, data: Dict, obj: Any) -> None:
        """Validate status change before editing."""
        from services.ai.usage_tracking import validate_status_change

        if "status" in data:
            await validate_status_change(request.state.session, "personality", obj.id, data["status"])

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["name", "display_name"]
    sortable_fields = ["id", "name", "display_name", "status", "usage_count", "created_at"]

    @link_row_action(
        name="edit_complete",
        text="Edit Complete",
        icon_class="fas fa-cogs",
    )
    def edit_complete_row_action(self, request: Request, pk: Any) -> str:
        """Link to edit personality JSON schema and placeholders."""
        return f"/qiao-dash/ai-personality/{pk}/edit-complete"

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
        JSONField("json_schema", label="JSON Schema", help_text="JSON schema for AI response validation"),
        IntegerField(
            "usage_count", label="Usage Count", help_text="Number of characters using this personality"
        ),
        IntegerField(
            "typing_speed",
            label="Typing Speed (CPM)",
            help_text="Characters per minute typing speed",
            required=True,
        ),
        IntegerEnumField(
            "status",
            enum=AIPersonalityStatus,
            label="Status",
            help_text="Active personalities can be used",
            required=True,
        ),
    ]


class AIPersonalityPlaceholderView(ModelView):
    """Enhanced AI Personality Placeholder view with proper field configuration."""

    exclude_fields_from_create = ["id", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "created_at", "updated_at"]
    exclude_fields_from_list = ["example_value"]

    def can_delete(self, request: Request) -> bool:
        return False

    fields_default_sort = [("personality_id", False), ("placeholder_key", False)]
    searchable_fields = ["placeholder_key", "display_name"]
    sortable_fields = [
        "id",
        "personality_id",
        "placeholder_key",
        "display_name",
        "is_required",
    ]

    fields = [
        StringField("id", label="ID", help_text="Internal placeholder ID"),
        HasOne(
            "personality",
            identity="ai_personality",
            label="AI Personality",
            help_text="AI personality this placeholder belongs to",
            required=True,
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
        IntegerEnumField(
            "is_required",
            enum=RequiredStatus,
            label="Required",
            help_text="Whether this placeholder must be filled",
        ),
    ]


class AICharacterView(ModelView):
    """Enhanced AI Character view with proper field configuration and chat test functionality."""

    exclude_fields_from_create = ["id", "qiao_id", "created_by", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "qiao_id", "created_by", "created_at", "updated_at"]
    exclude_fields_from_list = ["prompt_variables", "memory", "request_params"]

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

    async def before_create(self, request: Request, data: Dict[str, Any], obj: Any) -> None:
        """Auto-fill foreign keys and required fields before creating character."""
        from starlette_admin.exceptions import FormValidationError

        # Set created_by to 2 (Admin) for admin panel creations
        obj.created_by = 2

        # Auto-fill foreign keys from HasOne relationships
        # starlette-admin's HasOne sets the relationship object but not the FK field
        if hasattr(obj, "style") and obj.style is not None:
            obj.style_id = obj.style.id
        if hasattr(obj, "personality") and obj.personality is not None:
            obj.personality_id = obj.personality.id
        if hasattr(obj, "user") and obj.user is not None:
            obj.user_id = obj.user.id
            obj.user_qiao_id = obj.user.qiao_id
        else:
            # If user is not set, clear user_id and user_qiao_id
            obj.user_id = None
            obj.user_qiao_id = None

        # Validate required foreign keys
        errors = {}
        if not hasattr(obj, "style_id") or obj.style_id is None:
            errors["style"] = "AI Style is required"
        if not hasattr(obj, "personality_id") or obj.personality_id is None:
            errors["personality"] = "AI Personality is required"

        if errors:
            raise FormValidationError(errors)

    async def before_edit(self, request: Request, data: Dict[str, Any], obj: Any) -> None:
        """Auto-fill foreign keys before editing character."""
        from starlette_admin.exceptions import FormValidationError

        # Auto-fill foreign keys from HasOne relationships
        if hasattr(obj, "style") and obj.style is not None:
            obj.style_id = obj.style.id
        if hasattr(obj, "personality") and obj.personality is not None:
            obj.personality_id = obj.personality.id
        if hasattr(obj, "user") and obj.user is not None:
            obj.user_id = obj.user.id
            obj.user_qiao_id = obj.user.qiao_id
        else:
            # If user is not set or cleared, set to None
            obj.user_id = None
            obj.user_qiao_id = None

        # Validate required foreign keys
        errors = {}
        if not hasattr(obj, "style_id") or obj.style_id is None:
            errors["style"] = "AI Style is required"
        if not hasattr(obj, "personality_id") or obj.personality_id is None:
            errors["personality"] = "AI Personality is required"

        if errors:
            raise FormValidationError(errors)

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["qiao_id", "category"]
    sortable_fields = ["id", "qiao_id", "category", "status", "created_by", "created_at"]

    fields = [
        StringField("id", label="ID", help_text="Internal character ID"),
        StringField("qiao_id", label="Character ID", help_text="Unique character identifier"),
        StringField("category", label="Category", help_text="Character category classification"),
        HasOne(
            "user",
            identity="user",
            label="Owner User",
            help_text="User who owns this character (optional for system characters)",
            required=False,
        ),
        HasOne(
            "style",
            identity="ai_style",
            label="AI Style",
            help_text="AI style for this character",
            required=True,
        ),
        HasOne(
            "personality",
            identity="ai_personality",
            label="AI Personality",
            help_text="AI personality for this character",
            required=True,
        ),
        IntegerEnumField(
            "status",
            enum=AICharacterStatus,
            label="Status",
            help_text="Character status: Active characters can be used (default: Active)",
            required=True,
        ),
        TextAreaField(
            "memory",
            label="Memory Settings",
            help_text="Character-specific memory and background information",
        ),
        JSONField(
            "prompt_variables",
            label="Prompt Variables",
            help_text="Character-specific prompt variable values",
        ),
        IntegerEnumField(
            "score_offset_algorithm",
            enum=ScoreOffsetAlgorithm,
            label="Score Offset Algorithm",
            help_text="Algorithm for relationship score calculation (required, no default)",
            required=True,
        ),
        JSONField(
            "score_offset_params",
            label="Score Offset Parameters",
            help_text="Parameters for score offset algorithm",
        ),
        JSONField(
            "request_params",
            label="Request Parameters",
            help_text="LLM request parameters (temperature, max_tokens, etc.)",
        ),
        IntegerEnumField(
            "created_by",
            enum=AICharacterCreator,
            label="Created By",
            help_text="Who created this character",
        ),
    ]

    row_actions = ["view", "edit", "edit_json", "chat_test"]

    @link_row_action(
        name="edit_json",
        text="Edit JSON",
        icon_class="fas fa-cogs",
    )
    def edit_json_row_action(self, request: Request, pk: Any) -> str:
        """Link to edit character JSON fields."""
        return f"/qiao-dash/ai-character/{pk}/edit-json"

    @link_row_action(
        name="chat_test",
        text="Chat Test",
        icon_class="fas fa-flask",
    )
    def chat_test_row_action(self, request: Request, pk: Any) -> str:
        """Link to AI character chat test page."""
        return f"/qiao-dash/ai-character/{pk}/chat-test"


class AIStyleView(ModelView):
    """Enhanced AI Style view with proper field configuration."""

    exclude_fields_from_create = ["id", "usage_count", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "usage_count", "created_at", "updated_at"]

    def can_delete(self, request):
        return False

    async def before_edit(self, request: Request, data: Dict, obj: Any) -> None:
        """Validate status change before editing."""
        from services.ai.usage_tracking import validate_status_change

        if "status" in data:
            await validate_status_change(request.state.session, "style", obj.id, data["status"])

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["name", "display_name"]
    sortable_fields = ["id", "name", "display_name", "status", "usage_count", "created_at"]

    fields = [
        StringField("id", label="ID", help_text="Internal style ID"),
        StringField("name", label="Style Name", help_text="Unique identifier for the style", required=True),
        StringField(
            "display_name", label="Display Name", help_text="Human-readable name shown in UI", required=True
        ),
        IntegerField("usage_count", label="Usage Count", help_text="Number of characters using this style"),
        IntegerEnumField(
            "status",
            enum=AIStyleStatus,
            label="Status",
            help_text="Active styles can be used",
            required=True,
        ),
    ]

    row_actions = ["view", "edit", "edit_complete", "relationship_management"]

    @link_row_action(
        name="edit_complete",
        text="Edit Complete",
        icon_class="fas fa-cogs",
    )
    def edit_complete_row_action(self, request: Request, pk: Any) -> str:
        """Link to edit style complete (dimensions and indexes)."""
        return f"/qiao-dash/ai-style/{pk}/edit-complete"

    @link_row_action(
        name="relationship_management",
        text="Relationship Management",
        icon_class="fas fa-flask",
    )
    def relationship_management_row_action(self, request: Request, pk: Any) -> str:
        """Link to AI style relationship management page."""
        return f"/qiao-dash/ai-style/{pk}/score-algorithm-test"


class AIRelationshipView(ModelView):
    """Enhanced AI Relationship view with proper field configuration."""

    exclude_fields_from_create = ["id", "usage_count", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "usage_count", "created_at", "updated_at"]
    exclude_fields_from_list = ["prompt_fragment"]

    def can_delete(self, request):
        return False

    async def before_edit(self, request: Request, data: Dict, obj: Any) -> None:
        """Validate status change before editing."""
        from services.ai.usage_tracking import validate_status_change

        if "status" in data:
            await validate_status_change(request.state.session, "relationship", obj.id, data["status"])

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
        IntegerEnumField(
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

    async def before_create(self, request: Request, data: Dict[str, Any], obj: Any) -> None:
        """Auto-fill foreign keys before creating dimension."""
        from starlette_admin.exceptions import FormValidationError

        # Auto-fill style_id from HasOne relationship
        if hasattr(obj, "style") and obj.style is not None:
            obj.style_id = obj.style.id

        # Validate required foreign key
        if not hasattr(obj, "style_id") or obj.style_id is None:
            raise FormValidationError({"style": "AI Style is required"})

        # Validate initial_position range (0-1000 permille)
        errors = {}
        if hasattr(obj, "initial_position") and obj.initial_position is not None:
            if obj.initial_position < 0 or obj.initial_position > 1000:
                errors["initial_position"] = "Initial position must be between 0 and 1000 (permille)"

        if errors:
            raise FormValidationError(errors)

    async def before_edit(self, request: Request, data: Dict[str, Any], obj: Any) -> None:
        """Auto-fill foreign keys before editing dimension."""
        from starlette_admin.exceptions import FormValidationError

        # Auto-fill style_id from HasOne relationship
        if hasattr(obj, "style") and obj.style is not None:
            obj.style_id = obj.style.id

        # Validate initial_position range (0-1000 permille)
        errors = {}
        if hasattr(obj, "initial_position") and obj.initial_position is not None:
            if obj.initial_position < 0 or obj.initial_position > 1000:
                errors["initial_position"] = "Initial position must be between 0 and 1000 (permille)"

        if errors:
            raise FormValidationError(errors)

    fields_default_sort = [("style_id", False), ("name", False)]
    searchable_fields = ["name", "display_name"]
    sortable_fields = ["id", "style_id", "name", "display_name", "initial_position", "created_at"]

    fields = [
        StringField("id", label="ID", help_text="Internal dimension ID"),
        HasOne(
            "style",
            identity="ai_style",
            label="AI Style",
            help_text="AI style this dimension belongs to",
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

    async def before_create(self, request: Request, data: Dict[str, Any], obj: Any) -> None:
        """Auto-fill foreign keys before creating index."""
        from starlette_admin.exceptions import FormValidationError

        # Auto-fill foreign keys from HasOne relationships
        if hasattr(obj, "style") and obj.style is not None:
            obj.style_id = obj.style.id
        if hasattr(obj, "dimension") and obj.dimension is not None:
            obj.dimension_id = obj.dimension.id
            # Auto-fill dimension_name from dimension object
            if hasattr(obj.dimension, "name"):
                obj.dimension_name = obj.dimension.name
        if hasattr(obj, "relationship") and obj.relationship is not None:
            obj.relationship_id = obj.relationship.id

        # Validate required foreign keys
        errors = {}
        if not hasattr(obj, "style_id") or obj.style_id is None:
            errors["style"] = "AI Style is required"
        if not hasattr(obj, "dimension_id") or obj.dimension_id is None:
            errors["dimension"] = "Relationship Dimension is required"
        if not hasattr(obj, "relationship_id") or obj.relationship_id is None:
            errors["relationship"] = "Relationship Type is required"

        # Validate position ranges (0-1000 permille)
        if hasattr(obj, "start_position") and obj.start_position is not None:
            if obj.start_position < 0 or obj.start_position > 1000:
                errors["start_position"] = "Start position must be between 0 and 1000 (permille)"

        if hasattr(obj, "end_position") and obj.end_position is not None:
            if obj.end_position < 0 or obj.end_position > 1000:
                errors["end_position"] = "End position must be between 0 and 1000 (permille)"

        # Validate start_position < end_position
        if (
            hasattr(obj, "start_position")
            and obj.start_position is not None
            and hasattr(obj, "end_position")
            and obj.end_position is not None
        ):
            if obj.start_position >= obj.end_position:
                errors["end_position"] = "End position must be greater than start position"

        if errors:
            raise FormValidationError(errors)

    async def before_edit(self, request: Request, data: Dict[str, Any], obj: Any) -> None:
        """Auto-fill foreign keys before editing index."""
        from starlette_admin.exceptions import FormValidationError

        # Auto-fill foreign keys from HasOne relationships
        if hasattr(obj, "style") and obj.style is not None:
            obj.style_id = obj.style.id
        if hasattr(obj, "dimension") and obj.dimension is not None:
            obj.dimension_id = obj.dimension.id
            # Auto-fill dimension_name from dimension object
            if hasattr(obj.dimension, "name"):
                obj.dimension_name = obj.dimension.name
        if hasattr(obj, "relationship") and obj.relationship is not None:
            obj.relationship_id = obj.relationship.id

        # Validate position ranges (0-1000 permille)
        errors = {}
        if hasattr(obj, "start_position") and obj.start_position is not None:
            if obj.start_position < 0 or obj.start_position > 1000:
                errors["start_position"] = "Start position must be between 0 and 1000 (permille)"

        if hasattr(obj, "end_position") and obj.end_position is not None:
            if obj.end_position < 0 or obj.end_position > 1000:
                errors["end_position"] = "End position must be between 0 and 1000 (permille)"

        # Validate start_position < end_position
        if (
            hasattr(obj, "start_position")
            and obj.start_position is not None
            and hasattr(obj, "end_position")
            and obj.end_position is not None
        ):
            if obj.start_position >= obj.end_position:
                errors["end_position"] = "End position must be greater than start position"

        if errors:
            raise FormValidationError(errors)

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
        HasOne(
            "style",
            identity="ai_style",
            label="AI Style",
            help_text="AI style this index belongs to",
            required=True,
        ),
        HasOne(
            "dimension",
            identity="ai_relationship_dimension",
            label="Relationship Dimension",
            help_text="Relationship dimension",
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
        HasOne(
            "relationship",
            identity="ai_relationship",
            label="Relationship Type",
            help_text="Relationship type for this range",
            required=True,
        ),
        IntegerField(
            "priority", label="Priority", help_text="Priority level (higher number = higher priority)"
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

    async def before_create(self, request: Request, data: Dict[str, Any], obj: Any) -> None:
        """Auto-fill foreign keys before creating info template."""
        from starlette_admin.exceptions import FormValidationError

        # Auto-fill foreign keys from HasOne relationships
        if hasattr(obj, "style") and obj.style is not None:
            obj.style_id = obj.style.id
        if hasattr(obj, "personality") and obj.personality is not None:
            obj.personality_id = obj.personality.id
        if hasattr(obj, "profile") and obj.profile is not None:
            obj.profile_id = obj.profile.id

        # Validate required foreign keys
        errors = {}
        if not hasattr(obj, "style_id") or obj.style_id is None:
            errors["style"] = "AI Style is required"
        if not hasattr(obj, "personality_id") or obj.personality_id is None:
            errors["personality"] = "AI Personality is required"

        if errors:
            raise FormValidationError(errors)

    fields_default_sort = [("created_at", True)]
    searchable_fields = []
    sortable_fields = ["id", "style_id", "personality_id", "status", "is_reusable", "created_at"]

    fields = [
        StringField("id", label="ID", help_text="Internal info template ID"),
        HasOne(
            "style",
            identity="ai_style",
            label="AI Style",
            help_text="AI style for this template",
            required=True,
        ),
        HasOne(
            "personality",
            identity="ai_personality",
            label="AI Personality",
            help_text="AI personality for this template",
            required=True,
        ),
        TextAreaField(
            "memory",
            label="Memory Settings",
            help_text="Default memory settings for characters using this template",
        ),
        "prompt_variables",
        IntegerEnumField(
            "score_offset_algorithm",
            enum=ScoreOffsetAlgorithm,
            label="Score Offset Algorithm",
            help_text="Algorithm for relationship score calculation (optional)",
            required=False,
        ),
        "score_offset_params",
        IntegerEnumField(
            "is_reusable",
            enum=ReusableStatus,
            label="Reusable",
            help_text="Whether this template can be used multiple times",
            required=True,
        ),
        HasOne(
            "profile",
            identity="ai_profile_template",
            label="Profile Template",
            help_text="Associated profile template (for single-use templates)",
            required=False,
        ),
        IntegerEnumField(
            "status",
            enum=AIStyleStatus,
            label="Status",
            help_text="Active templates can be used",
            required=True,
        ),
    ]

    row_actions = ["view", "edit", "edit_json"]

    @link_row_action(
        name="edit_json",
        text="Edit JSON",
        icon_class="fas fa-cogs",
    )
    def edit_json_row_action(self, request: Request, pk: Any) -> str:
        """Link to edit info template JSON fields."""
        return f"/qiao-dash/ai-info-template/{pk}/edit-json"


class AIProfileTemplateView(ModelView):
    """Enhanced AI Profile Template view with proper field configuration."""

    exclude_fields_from_create = ["id", "qiao_id", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "qiao_id", "created_at", "updated_at"]

    def can_delete(self, request):
        return False

    async def before_create(self, request: Request, data: Dict[str, Any], obj: Any) -> None:
        """Auto-fill foreign keys and generate IDs before creating profile template."""
        from starlette_admin.exceptions import FormValidationError

        # Auto-fill info_id from HasOne relationship
        if hasattr(obj, "info") and obj.info is not None:
            obj.info_id = obj.info.id

        # Validate required foreign key
        if not hasattr(obj, "info_id") or obj.info_id is None:
            raise FormValidationError({"info": "Info Template is required"})

        # Generate qiao_id if not provided
        if not hasattr(obj, "qiao_id") or not obj.qiao_id:
            from models.base import generate_qiao_id

            obj.qiao_id = generate_qiao_id()

        # Generate id if not provided (Snowflake ID)
        if not hasattr(obj, "id") or not obj.id:
            from utils.snowflake import generate_snowflake_id

            obj.id = generate_snowflake_id()

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
        HasOne(
            "info",
            identity="ai_info_template",
            label="Info Template",
            help_text="Associated AI info template",
            required=True,
        ),
        StringField("nickname", label="Nickname", help_text="Character nickname"),
        IntegerEnumField(
            "gender", enum=Gender, label="Gender", help_text="Character gender (optional)", required=False
        ),
        StringField("avatar_url", label="Avatar URL", help_text="Character avatar image URL"),
        TextAreaField("bio", label="Bio", help_text="Character biography and description"),
        StringField("region", label="Region", help_text="Character location/region"),
        IntegerEnumField(
            "is_reusable",
            enum=ReusableStatus,
            label="Reusable",
            help_text="Whether this template can be used multiple times",
            required=True,
        ),
        IntegerEnumField(
            "status",
            enum=AIStyleStatus,
            label="Status",
            help_text="Active templates can be used",
            required=True,
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
    exclude_fields_from_detail = []  # Show all fields in detail view

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
        "request_type",
        "status",
        "token_count",
        "response_time",
        "created_at",
        "completed_at",
    ]

    fields = [
        StringField("id", label="ID", help_text="Internal request log ID"),
        StringField("character_id", label="AI Character ID", help_text="AI character snowflake ID"),
        StringField("user_id", label="User ID", help_text="User snowflake ID"),
        IntegerField("style_id", label="AI Style ID"),
        IntegerField("personality_id", label="AI Personality ID"),
        StringField("request_type", label="Request Type", help_text="production or test"),
        StringField("provider_name", label="Provider", help_text="LLM provider name"),
        StringField("model_name", label="Model", help_text="Model name used"),
        JSONField("request", label="Request", help_text="Request content in JSON format"),
        JSONField("response", label="Response", help_text="Response content in JSON format"),
        IntegerEnumField("status", enum=AIRequestStatus, label="Status"),
        IntegerField("token_count", label="Token Count"),
        IntegerField("response_time", label="Response Time (ms)"),
        "created_at",
        "completed_at",
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
