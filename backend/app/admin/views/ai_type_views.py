"""
AI Type admin views.

Provides a lightweight interface for managing the new ai_types table.
"""

from typing import Sequence
from starlette.requests import Request
from starlette_admin.contrib.sqla import ModelView
from starlette_admin import StringField, TextAreaField
from admin.fields import LocalDateTimeField

from models.ai.template import AIType


class AITypeView(ModelView):
    """CRUD view for ai_types entries."""

    exclude_fields_from_create = ["id", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "created_at", "updated_at"]
    exclude_fields_from_list: Sequence[str] = []

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["display_name"]
    sortable_fields = ["id", "display_name", "created_at", "updated_at"]

    fields = [
        StringField("id", label="ID", help_text="Internal AI type identifier"),
        StringField("display_name", label="Display Name", help_text="Admin display label"),
        TextAreaField("description", label="Description", help_text="Optional description"),
        LocalDateTimeField("created_at", label="Created At", help_text="Creation timestamp"),
        LocalDateTimeField("updated_at", label="Updated At", help_text="Last update timestamp"),
    ]

    def can_delete(self, request: Request) -> bool:  # type: ignore[override]
        return False


ai_type_view = AITypeView(
    AIType,
    name="AI Types",
    label="Types",
    icon="fa fa-tags",
    identity="ai_type",
)

AI_TYPE_VIEWS = [
    ai_type_view,
]
