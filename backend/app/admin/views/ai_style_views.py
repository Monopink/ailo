"""
AI Style and Relationship admin views.

This module contains Starlette-Admin views for AI style and relationship system.
"""

from typing import Any, ClassVar

from starlette.requests import Request
from starlette_admin import EnumField, FloatField, HasOne, IntegerField, StringField, TextAreaField
from starlette_admin.actions import link_row_action
from starlette_admin.contrib.sqla import ModelView
from starlette_admin.exceptions import FormValidationError

from app.admin.fields import LocalDateTimeField
from app.admin.views.base import IntegerEnumField
from app.enums import AIStyleStatus
from app.models.ai.style import (
    AIDimension,
    AIDimensionRelationshipMapping,
    AIRelationship,
    AIStyle,
    AIStyleDimension,
)


class _DimensionDisplayNameField(StringField):
    """Computed field to display the dimension display_name."""

    def __init__(self, name: str = "dimension_display_name", label: str = "Dimension Name") -> None:
        super().__init__(name=name, label=label)
        self.read_only = True
        self.searchable = False
        self.orderable = False

    async def parse_obj(self, _request: Request, obj: Any) -> str:
        try:
            if hasattr(obj, "dimension") and obj.dimension is not None:
                return str(getattr(obj.dimension, "display_name", "") or "")
            return ""
        except Exception:
            return ""


class AIStyleView(ModelView):
    """Enhanced AI Style view with proper field configuration."""

    exclude_fields_from_create: ClassVar[list[str]] = ["id", "created_at", "updated_at"]
    exclude_fields_from_edit: ClassVar[list[str]] = ["id", "created_at", "updated_at"]

    def is_active(self, request: Request) -> bool:
        """Check if current page is related to this model (including advanced-edit and test)."""
        # Standard identity check for list/edit/detail pages
        if request.path_params.get("identity", None) == self.identity:
            return True

        # Check for advanced-edit or test page with exact identity match
        path = request.scope["path"]
        return f"/{self.identity}/advanced-edit/" in path or f"/{self.identity}/test/" in path

    def can_delete(self, _request: Request) -> bool:
        return False

    fields_default_sort: ClassVar[list[tuple[str, bool]]] = [("created_at", True)]
    searchable_fields: ClassVar[list[str]] = ["display_name"]
    sortable_fields: ClassVar[list[str]] = [
        "id",
        "display_name",
        "status",
        "created_at",
        "updated_at",
    ]

    fields: ClassVar[list[object]] = [
        StringField("id", label="ID", help_text="Internal style ID"),
        StringField(
            "display_name",
            label="Display Name",
            help_text="Human-readable name shown in UI",
            required=True,
        ),
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

    row_actions: ClassVar[list[str]] = ["view", "edit", "advanced_edit", "score_algorithm_test"]

    @link_row_action(
        name="advanced_edit",
        text="Advanced Edit",
        icon_class="fas fa-cogs",
    )
    def advanced_edit_row_action(self, _request: Request, pk: Any) -> str:
        """Link to style advanced edit (dimensions and mappings)."""
        return f"/qiao-dash/ai_style/advanced-edit/{pk}"

    @link_row_action(
        name="score_algorithm_test",
        text="Score Algorithm Test",
        icon_class="fas fa-flask",
    )
    def score_algorithm_test_row_action(self, _request: Request, pk: Any) -> str:
        """Link to AI style score algorithm test page."""
        return f"/qiao-dash/ai_style/test/{pk}"


MIN_WAKE_TIME_MS = 500
MIN_POSITION = 0
MAX_POSITION = 1000
MIN_NO_REPLY_PROB = 0.0
MAX_NO_REPLY_PROB = 1.0

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


def _validate_relationship_payload(obj: Any) -> dict[str, str]:
    """Collect validation errors for relationship timing fields."""

    errors: dict[str, str] = {}
    wake_time_min = getattr(obj, "wake_time_min_ms", None)
    if wake_time_min is not None and wake_time_min < MIN_WAKE_TIME_MS:
        errors["wake_time_min_ms"] = f"Minimum wake time must be at least {MIN_WAKE_TIME_MS}ms"

    wake_time_max = getattr(obj, "wake_time_max_ms", None)
    if wake_time_min is not None and wake_time_max is not None and wake_time_max < wake_time_min:
        errors["wake_time_max_ms"] = (
            "Maximum wake time must be greater than or equal to minimum wake time"
        )

    wake_time_bias = getattr(obj, "wake_time_bias", None)
    if wake_time_bias is not None and not str(wake_time_bias).strip():
        errors["wake_time_bias"] = "Wake time bias cannot be empty"

    wake_window = getattr(obj, "wake_window_ms", None)
    if wake_window is not None and wake_window < MIN_POSITION:
        errors["wake_window_ms"] = "Wake window must be non-negative"

    wake_time_adjustment = getattr(obj, "wake_time_adjustment", None)
    if wake_time_adjustment is not None and not str(wake_time_adjustment).strip():
        errors["wake_time_adjustment"] = "Wake time adjustment cannot be empty"

    no_reply_probability = getattr(obj, "no_reply_probability", None)
    if no_reply_probability is not None and not (
        MIN_NO_REPLY_PROB <= no_reply_probability <= MAX_NO_REPLY_PROB
    ):
        errors["no_reply_probability"] = "No reply probability must be between 0.0 and 1.0"

    followup_delay = getattr(obj, "followup_delay_ms", None)
    if followup_delay is not None and followup_delay < MIN_POSITION:
        errors["followup_delay_ms"] = "Followup delay must be non-negative"

    return errors


def _validate_position_value(value: Any, field_name: str, errors: dict[str, str]) -> None:
    """Ensure a position stays inside the valid range."""

    if value is None:
        return
    if not (MIN_POSITION <= value <= MAX_POSITION):
        errors[field_name] = (
            f"{field_name.replace('_', ' ').title()} must be between "
            f"{MIN_POSITION} and {MAX_POSITION} (permille)"
        )


def _validate_position_order(start_value: Any, end_value: Any, errors: dict[str, str]) -> None:
    """Ensure start position is less than end position."""

    if start_value is None or end_value is None:
        return
    if start_value >= end_value:
        errors["end_position"] = "End position must be greater than start position"


class AIRelationshipView(ModelView):
    """Enhanced AI Relationship view with proper field configuration."""

    exclude_fields_from_create: ClassVar[list[str]] = ["id", "created_at", "updated_at"]
    exclude_fields_from_edit: ClassVar[list[str]] = ["id", "created_at", "updated_at"]
    exclude_fields_from_list: ClassVar[list[str]] = []

    def can_delete(self, _request: Request) -> bool:
        return False

    async def before_create(self, _request: Request, _data: dict[str, Any], obj: Any) -> None:
        """Validate constraints before creating relationship."""
        errors = _validate_relationship_payload(obj)
        if errors:
            raise FormValidationError(errors)

    async def before_edit(self, _request: Request, _data: dict[str, Any], obj: Any) -> None:
        """Validate constraints before editing relationship."""
        errors = _validate_relationship_payload(obj)
        if errors:
            raise FormValidationError(errors)

    fields_default_sort: ClassVar[list[tuple[str, bool]]] = [("created_at", True)]
    searchable_fields: ClassVar[list[str]] = ["display_name", "prompt_fragment"]
    sortable_fields: ClassVar[list[str]] = [
        "id",
        "display_name",
        "wake_time_min_ms",
        "wake_time_max_ms",
        "wake_window_ms",
        "no_reply_probability",
        "status",
        "created_at",
        "updated_at",
    ]

    fields: ClassVar[list[object]] = [
        StringField("id", label="ID", help_text="Internal relationship ID"),
        StringField(
            "display_name",
            label="Display Name",
            help_text="Human-readable name shown in UI",
            required=True,
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
            help_text=(
                "Either keep the wait or apply the random-half algorithm "
                "(50% chance to shorten)."
            ),
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
        LocalDateTimeField("created_at", label="Created At", help_text="Creation time"),
        LocalDateTimeField("updated_at", label="Updated At", help_text="Last update time"),
    ]


class AIStyleDimensionView(ModelView):
    """Enhanced AI Style Dimension view with proper field configuration."""

    exclude_fields_from_create: ClassVar[list[str]] = ["id", "created_at", "updated_at"]
    exclude_fields_from_edit: ClassVar[list[str]] = ["id", "created_at", "updated_at"]

    def can_delete(self, _request: Request) -> bool:
        return False

    async def before_create(self, _request: Request, _data: dict[str, Any], obj: Any) -> None:
        """Auto-fill foreign keys before creating dimension."""
        # Auto-fill style_id from HasOne relationship
        if hasattr(obj, "style") and obj.style is not None:
            obj.style_id = obj.style.id

        # Validate required foreign key
        if not hasattr(obj, "style_id") or obj.style_id is None:
            raise FormValidationError({"style": "AI Style is required"})

        # Validate initial_position range (0-1000 permille)
        errors: dict[str, str] = {}
        _validate_position_value(getattr(obj, "initial_position", None), "initial_position", errors)

        if errors:
            raise FormValidationError(errors)

    async def before_edit(self, _request: Request, _data: dict[str, Any], obj: Any) -> None:
        """Auto-fill foreign keys before editing dimension."""
        # Auto-fill style_id from HasOne relationship
        if hasattr(obj, "style") and obj.style is not None:
            obj.style_id = obj.style.id

        # Validate initial_position range (0-1000 permille)
        errors: dict[str, str] = {}
        _validate_position_value(getattr(obj, "initial_position", None), "initial_position", errors)

        if errors:
            raise FormValidationError(errors)

    fields_default_sort: ClassVar[list[tuple[str, bool]]] = [("style_id", False)]
    searchable_fields: ClassVar[list[str]] = []
    sortable_fields: ClassVar[list[str]] = ["id", "style_id", "initial_position", "created_at"]

    fields: ClassVar[list[object]] = [
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

    exclude_fields_from_create: ClassVar[list[str]] = ["id", "created_at", "updated_at"]
    exclude_fields_from_edit: ClassVar[list[str]] = ["id", "created_at", "updated_at"]

    fields_default_sort: ClassVar[list[tuple[str, bool]]] = [("name", False)]
    searchable_fields: ClassVar[list[str]] = ["name", "display_name"]
    sortable_fields: ClassVar[list[str]] = ["id", "name", "display_name", "created_at"]

    fields: ClassVar[list[object]] = [
        StringField("id", label="ID", help_text="Internal dimension ID"),
        StringField("name", label="Name", help_text="Unique dimension name", required=True),
        StringField("display_name", label="Display Name", help_text="Shown in UI"),
        TextAreaField("description", label="Description", help_text="Optional description"),
    ]


class AIDimensionRelationshipMappingView(ModelView):
    """AI Dimension Relationship Mapping view with position axis visualization."""

    exclude_fields_from_create: ClassVar[list[str]] = ["id", "created_at", "updated_at"]
    exclude_fields_from_edit: ClassVar[list[str]] = [
        "id",
        "dimension_display_name",
        "created_at",
        "updated_at",
    ]

    def can_delete(self, _request: Request) -> bool:
        return False

    async def before_create(self, _request: Request, _data: dict[str, Any], obj: Any) -> None:
        """Auto-fill foreign keys before creating mapping."""
        # Auto-fill foreign keys from HasOne relationships
        if hasattr(obj, "dimension") and obj.dimension is not None:
            obj.dimension_id = obj.dimension.id
            # No separate name column stored; use relation only
        if hasattr(obj, "relationship") and obj.relationship is not None:
            obj.relationship_id = obj.relationship.id

        # Validate required foreign keys
        errors: dict[str, str] = {}
        if not hasattr(obj, "dimension_id") or obj.dimension_id is None:
            errors["dimension"] = "Relationship Dimension is required"
        if not hasattr(obj, "relationship_id") or obj.relationship_id is None:
            errors["relationship"] = "Relationship Type is required"

        start_position = getattr(obj, "start_position", None)
        end_position = getattr(obj, "end_position", None)
        _validate_position_value(start_position, "start_position", errors)
        _validate_position_value(end_position, "end_position", errors)
        _validate_position_order(start_position, end_position, errors)

        if errors:
            raise FormValidationError(errors)

    async def before_edit(self, _request: Request, _data: dict[str, Any], obj: Any) -> None:
        """Auto-fill foreign keys before editing mapping."""
        # Auto-fill foreign keys from HasOne relationships
        if hasattr(obj, "dimension") and obj.dimension is not None:
            obj.dimension_id = obj.dimension.id
            # Auto-fill dimension_name from dimension object
            if hasattr(obj.dimension, "name"):
                obj.dimension_name = obj.dimension.name
        if hasattr(obj, "relationship") and obj.relationship is not None:
            obj.relationship_id = obj.relationship.id

        errors: dict[str, str] = {}
        start_position = getattr(obj, "start_position", None)
        end_position = getattr(obj, "end_position", None)
        _validate_position_value(start_position, "start_position", errors)
        _validate_position_value(end_position, "end_position", errors)
        _validate_position_order(start_position, end_position, errors)

        if errors:
            raise FormValidationError(errors)

    fields_default_sort: ClassVar[list[tuple[str, bool]]] = [("start_position", False)]
    searchable_fields: ClassVar[list[str]] = []
    sortable_fields: ClassVar[list[str]] = [
        "id",
        "start_position",
        "end_position",
        "relationship_id",
        "priority",
        "created_at",
        "updated_at",
    ]

    fields: ClassVar[list[object]] = [
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
            "priority",
            label="Priority",
            help_text="Priority level (higher number = higher priority)",
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
