"""
AI Style and Relationship admin views.

This module contains Starlette-Admin views for AI style and relationship system.
"""

from typing import Any, Dict
from starlette.requests import Request
from starlette_admin.contrib.sqla import ModelView
from starlette_admin import IntegerField, StringField, TextAreaField, HasOne, FloatField, EnumField
from admin.fields import LocalDateTimeField
from starlette_admin.actions import link_row_action
from starlette_admin.exceptions import FormValidationError

from models.ai.style import (
    AIStyle,
    AIRelationship,
    AIStyleDimension,
    AIDimension,
    AIDimensionRelationshipMapping,
)
from admin.views.base import IntegerEnumField
from enums import AIStyleStatus


class _DimensionDisplayNameField(StringField):
    """Computed field to display the dimension display_name."""

    def __init__(self, name: str = "dimension_display_name", label: str = "Dimension Name"):
        super().__init__(name=name, label=label)
        self.read_only = True
        self.searchable = False
        self.orderable = False

    async def parse_obj(self, request, obj):  # type: ignore[override]
        try:
            if hasattr(obj, "dimension") and obj.dimension is not None:
                return str(getattr(obj.dimension, "display_name", "") or "")
            return ""
        except Exception:
            return ""


class AIStyleView(ModelView):
    """Enhanced AI Style view with proper field configuration."""

    exclude_fields_from_create = ["id", "usage_count", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "usage_count", "created_at", "updated_at"]

    def is_active(self, request: Request) -> bool:
        """Check if current page is related to this model (including advanced-edit and test)."""
        # Standard identity check for list/edit/detail pages
        if request.path_params.get("identity", None) == self.identity:
            return True

        # Check for advanced-edit or test page with exact identity match
        path = request.scope["path"]
        return f"/{self.identity}/advanced-edit/" in path or f"/{self.identity}/test/" in path

    def can_delete(self, request):
        return False

    async def before_edit(self, request: Request, data: Dict, obj: Any) -> None:
        """Validate status change before editing."""
        from services.ai.usage_tracking import validate_status_change

        if "status" in data:
            await validate_status_change(request.state.session, "style", obj.id, data["status"])

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["name", "display_name"]
    sortable_fields = ["id", "name", "display_name", "status", "usage_count", "created_at", "updated_at"]

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
        LocalDateTimeField("created_at", label="Created At", help_text="Creation time"),
        LocalDateTimeField("updated_at", label="Updated At", help_text="Last update time"),
    ]

    row_actions = ["view", "edit", "advanced_edit", "score_algorithm_test"]

    @link_row_action(
        name="advanced_edit",
        text="Advanced Edit",
        icon_class="fas fa-cogs",
    )
    def advanced_edit_row_action(self, request: Request, pk: Any) -> str:
        """Link to style advanced edit (dimensions and mappings)."""
        return f"/qiao-dash/ai_style/advanced-edit/{pk}"

    @link_row_action(
        name="score_algorithm_test",
        text="Score Algorithm Test",
        icon_class="fas fa-flask",
    )
    def score_algorithm_test_row_action(self, request: Request, pk: Any) -> str:
        """Link to AI style score algorithm test page."""
        return f"/qiao-dash/ai_style/test/{pk}"


WAKE_BIAS_CHOICES = [
    ("balanced", "Balanced"),
    ("centered", "Centered"),
    ("fast", "Fast"),
    ("slow", "Slow"),
    ("very_fast", "Very Fast"),
    ("very_slow", "Very Slow"),
]

WAKE_ADJUSTMENT_CHOICES = [
    ("none", "No Adjustment (keep full wait, ≥1s)"),
    ("random_half", "Random Half (50% chance to shorten)"),
]


class AIRelationshipView(ModelView):
    """Enhanced AI Relationship view with proper field configuration."""

    exclude_fields_from_create = ["id", "usage_count", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "usage_count", "created_at", "updated_at"]
    exclude_fields_from_list = []

    def can_delete(self, request):
        return False

    async def before_edit(self, request: Request, data: Dict, obj: Any) -> None:
        """Validate status change before editing."""
        from services.ai.usage_tracking import validate_status_change

        if "status" in data:
            await validate_status_change(request.state.session, "relationship", obj.id, data["status"])

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["name", "display_name"]
    sortable_fields = [
        "id",
        "name",
        "display_name",
        "wake_time_min_ms",
        "wake_time_max_ms",
        "wake_window_ms",
        "no_reply_probability",
        "usage_count",
        "status",
        "created_at",
        "updated_at",
    ]

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
        IntegerField(
            "wake_time_min_ms",
            label="Wake Time Min (ms)",
            help_text="Minimum wake delay; must be ≥500",
            required=True,
        ),
        IntegerField(
            "wake_time_max_ms",
            label="Wake Time Max (ms)",
            help_text="Maximum wake delay; must be ≥ min",
            required=True,
        ),
        EnumField(
            "wake_time_bias",
            choices=WAKE_BIAS_CHOICES,
            label="Wake Bias",
            help_text="Distribution bias for wake sampling",
            required=True,
        ),
        IntegerField(
            "wake_window_ms",
            label="Wake Window (ms)",
            help_text="Skip wake if last user message within this window",
            required=True,
        ),
        EnumField(
            "wake_time_adjustment",
            choices=WAKE_ADJUSTMENT_CHOICES,
            label="Wake Adjustment",
            help_text="Either keep the wait or apply the random-half algorithm (50% chance to shorten)",
            required=True,
        ),
        FloatField(
            "no_reply_probability",
            label="No Reply Probability",
            help_text="Chance of skipping reply after wake (0.0–1.0)",
            required=True,
        ),
        IntegerField(
            "followup_delay_ms",
            label="Followup Delay (ms)",
            help_text="Wait time between outgoing and followup messages",
            required=True,
        ),
        IntegerEnumField(
            "status",
            enum=AIStyleStatus,
            label="Status",
            help_text="Active relationships can be used",
            required=True,
        ),
        IntegerField("usage_count", label="Usage Count", help_text="Usage count"),
        LocalDateTimeField("created_at", label="Created At", help_text="Creation time"),
        LocalDateTimeField("updated_at", label="Updated At", help_text="Last update time"),
    ]


class AIStyleDimensionView(ModelView):
    """Enhanced AI Style Dimension view with proper field configuration."""

    exclude_fields_from_create = ["id", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "created_at", "updated_at"]

    def can_delete(self, request):
        return False

    async def before_create(self, request: Request, data: Dict[str, Any], obj: Any) -> None:
        """Auto-fill foreign keys before creating dimension."""
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

    fields_default_sort = [("style_id", False)]
    searchable_fields = []
    sortable_fields = ["id", "style_id", "initial_position", "created_at"]

    fields = [
        StringField("id", label="ID", help_text="Internal dimension ID"),
        HasOne(
            "style",
            identity="ai_style",
            label="AI Style",
            help_text="AI style this dimension belongs to",
            required=True,
        ),
        HasOne(
            "dimension",
            identity="ai_dimension",
            label="Dimension",
            help_text="Select a dimension",
            required=True,
        ),
        IntegerField(
            "initial_position",
            label="Initial Position",
            help_text="Initial position value (0-1000 permille)",
            required=True,
        ),
        LocalDateTimeField("created_at", label="Created At", help_text="Creation time"),
    ]


class AIDimensionView(ModelView):
    """AI Dimension view."""

    exclude_fields_from_create = ["id", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "created_at", "updated_at"]

    fields_default_sort = [("name", False)]
    searchable_fields = ["name", "display_name"]
    sortable_fields = ["id", "name", "display_name", "created_at"]

    fields = [
        StringField("id", label="ID", help_text="Internal dimension ID"),
        StringField("name", label="Name", help_text="Unique dimension name", required=True),
        StringField("display_name", label="Display Name", help_text="Shown in UI"),
        TextAreaField("description", label="Description", help_text="Optional description"),
    ]


class AIDimensionRelationshipMappingView(ModelView):
    """AI Dimension Relationship Mapping view with position axis visualization."""

    exclude_fields_from_create = ["id", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "dimension_display_name", "created_at", "updated_at"]

    def can_delete(self, request):
        return False

    async def before_create(self, request: Request, data: Dict[str, Any], obj: Any) -> None:
        """Auto-fill foreign keys before creating mapping."""
        # Auto-fill foreign keys from HasOne relationships
        if hasattr(obj, "dimension") and obj.dimension is not None:
            obj.dimension_id = obj.dimension.id
            # No separate name column stored; use relation only
        if hasattr(obj, "relationship") and obj.relationship is not None:
            obj.relationship_id = obj.relationship.id

        # Validate required foreign keys
        errors = {}
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
        """Auto-fill foreign keys before editing mapping."""
        # Auto-fill foreign keys from HasOne relationships
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

    fields_default_sort = [("start_position", False)]
    searchable_fields = []
    sortable_fields = [
        "id",
        "start_position",
        "end_position",
        "relationship_id",
        "priority",
        "created_at",
        "updated_at",
    ]

    fields = [
        StringField("id", label="ID", help_text="Internal mapping ID"),
        HasOne(
            "dimension",
            identity="ai_dimension",
            label="Dimension",
            help_text="Dimension",
            required=True,
        ),
        _DimensionDisplayNameField(),
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
        LocalDateTimeField("created_at", label="Created At", help_text="Creation time"),
        LocalDateTimeField("updated_at", label="Updated At", help_text="Last update time"),
    ]


# Create view instances
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

ai_style_dimension_view = AIStyleDimensionView(
    AIStyleDimension,
    name="AI Style Dimensions",
    label="Style Dimensions",
    icon="fa fa-ruler",
    identity="ai_style_dimension",
)

ai_dimension_view = AIDimensionView(
    AIDimension,
    name="AI Dimensions",
    label="Dimensions",
    icon="fa fa-sliders-h",
    identity="ai_dimension",
)

ai_dimension_relationship_mapping_view = AIDimensionRelationshipMappingView(
    AIDimensionRelationshipMapping,
    name="AI Dimension Relationship Mappings",
    label="Relationship Mappings",
    icon="fa fa-sitemap",
    identity="ai_dimension_relationship_mapping",
)

# Export style and relationship views
AI_STYLE_VIEWS = [
    ai_style_view,
    ai_relationship_view,
    ai_dimension_view,
    ai_style_dimension_view,
    ai_dimension_relationship_mapping_view,
]
