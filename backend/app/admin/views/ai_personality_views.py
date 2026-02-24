"""AI Personality admin views.

This module contains Starlette-Admin views for AI personality system.
"""

from typing import Any, ClassVar

from starlette.requests import Request
from starlette_admin import DateTimeField, HasOne, StringField, TextAreaField
from starlette_admin.actions import link_row_action
from starlette_admin.contrib.sqla import ModelView
from starlette_admin.fields import JSONField

from app.admin.views.base import IntegerEnumField
from app.enums import AIPersonalityStatus, RequiredStatus
from app.models.ai.personality import AIPersonality, AIPersonalityPlaceholder


class AIPersonalityView(ModelView):
    """Enhanced AI Personality view with proper field configuration."""

    exclude_fields_from_create: ClassVar[list[str]] = ["id", "created_at", "updated_at"]
    exclude_fields_from_edit: ClassVar[list[str]] = ["id", "created_at", "updated_at"]
    exclude_fields_from_list: ClassVar[list[str]] = []

    row_actions: ClassVar[list[str]] = ["view", "edit", "advanced_edit"]

    def is_active(self, request: Request) -> bool:
        """Check if current page is related to this model (including advanced-edit)."""
        # Standard identity check for list/edit/detail pages
        if request.path_params.get("identity", None) == self.identity:
            return True

        # Check for advanced-edit page with exact identity match
        path = request.scope["path"]
        return f"/{self.identity}/advanced-edit/" in path

    def can_delete(self, _request: Request) -> bool:
        return False

    fields_default_sort: ClassVar[list[tuple[str, bool]]] = [("created_at", True)]
    searchable_fields: ClassVar[list[str]] = ["display_name", "prompt"]
    sortable_fields: ClassVar[list[str]] = [
        "id",
        "display_name",
        "status",
        "created_at",
        "updated_at",
    ]

    @link_row_action(
        name="advanced_edit",
        text="Advanced Edit",
        icon_class="fas fa-cogs",
    )
    def advanced_edit_row_action(self, _request: Request, pk: Any) -> str:
        """Link to edit personality JSON schema and placeholders."""
        return f"/qiao-dash/ai_personality/advanced-edit/{pk}"

    fields: ClassVar[list[object]] = [
        StringField("id", label="ID", help_text="Internal personality ID"),
        StringField(
            "display_name",
            label="Display Name",
            help_text="Human-readable name shown in UI",
            required=True,
        ),
        TextAreaField(
            "prompt",
            label="Personality Prompt",
            help_text="Template for AI personality behavior",
            required=True,
        ),
        JSONField(
            "json_schema",
            label="JSON Schema",
            help_text="JSON schema for AI response validation",
        ),
        IntegerEnumField(
            "status",
            enum=AIPersonalityStatus,
            label="Status",
            help_text="Active personalities can be used",
            required=True,
        ),
        DateTimeField("created_at", label="Created At", help_text="Creation time"),
        DateTimeField("updated_at", label="Updated At", help_text="Last update time"),
    ]


class AIPersonalityPlaceholderView(ModelView):
    """Enhanced AI Personality Placeholder view with proper field configuration."""

    exclude_fields_from_create: ClassVar[list[str]] = ["id", "created_at", "updated_at"]
    exclude_fields_from_edit: ClassVar[list[str]] = ["id", "created_at", "updated_at"]
    exclude_fields_from_list: ClassVar[list[str]] = []

    def can_delete(self, _request: Request) -> bool:
        return False

    fields_default_sort: ClassVar[list[tuple[str, bool]]] = [
        ("personality_id", False),
        ("placeholder_key", False),
    ]
    searchable_fields: ClassVar[list[str]] = ["placeholder_key", "display_name"]
    sortable_fields: ClassVar[list[str]] = [
        "id",
        "personality_id",
        "placeholder_key",
        "display_name",
        "is_required",
        "created_at",
        "updated_at",
    ]

    fields: ClassVar[list[object]] = [
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
            "display_name",
            label="Display Name",
            help_text="Human-readable name for this placeholder",
        ),
        StringField(
            "description",
            label="Description",
            help_text="Explanation of what this placeholder represents",
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
        DateTimeField("created_at", label="Created At"),
        DateTimeField("updated_at", label="Updated At"),
    ]


# Create view instances
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

# Export personality views
AI_PERSONALITY_VIEWS = [
    ai_personality_view,
    ai_personality_placeholder_view,
]
