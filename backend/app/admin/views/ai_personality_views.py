"""
AI Personality admin views.

This module contains Starlette-Admin views for AI personality system.
"""

from typing import Any, Dict
from starlette.requests import Request
from starlette_admin.contrib.sqla import ModelView
from starlette_admin import IntegerField, StringField, TextAreaField, HasOne
from starlette_admin.actions import link_row_action
from starlette_admin.fields import JSONField
from admin.fields import LocalDateTimeField

from models.ai.personality import AIPersonality, AIPersonalityPlaceholder
from admin.views.base import IntegerEnumField
from enums import AIPersonalityStatus, RequiredStatus


class AIPersonalityView(ModelView):
    """Enhanced AI Personality view with proper field configuration."""

    exclude_fields_from_create = ["id", "usage_count", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "usage_count", "created_at", "updated_at"]
    exclude_fields_from_list = []

    row_actions = ["view", "edit", "advanced_edit"]

    def is_active(self, request: Request) -> bool:
        """Check if current page is related to this model (including advanced-edit)."""
        # Standard identity check for list/edit/detail pages
        if request.path_params.get("identity", None) == self.identity:
            return True

        # Check for advanced-edit page with exact identity match
        path = request.scope["path"]
        return f"/{self.identity}/advanced-edit/" in path

    def can_delete(self, request: Request) -> bool:
        return False

    async def before_edit(self, request: Request, data: Dict, obj: Any) -> None:
        """Validate status change before editing."""
        from services.ai.usage_tracking import validate_status_change

        if "status" in data:
            await validate_status_change(request.state.session, "personality", obj.id, data["status"])

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["name", "display_name"]
    sortable_fields = ["id", "name", "display_name", "status", "usage_count", "created_at", "updated_at"]

    @link_row_action(
        name="advanced_edit",
        text="Advanced Edit",
        icon_class="fas fa-cogs",
    )
    def advanced_edit_row_action(self, request: Request, pk: Any) -> str:
        """Link to edit personality JSON schema and placeholders."""
        return f"/qiao-dash/ai_personality/advanced-edit/{pk}"

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
        LocalDateTimeField("created_at", label="Created At", help_text="Creation time"),
        LocalDateTimeField("updated_at", label="Updated At", help_text="Last update time"),
    ]


class AIPersonalityPlaceholderView(ModelView):
    """Enhanced AI Personality Placeholder view with proper field configuration."""

    exclude_fields_from_create = ["id", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "created_at", "updated_at"]
    exclude_fields_from_list = []

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
        "created_at",
        "updated_at",
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
        LocalDateTimeField("created_at", label="Created At"),
        LocalDateTimeField("updated_at", label="Updated At"),
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
