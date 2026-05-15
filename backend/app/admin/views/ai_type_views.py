"""AI Type admin views.

Provides a lightweight interface for managing the new ai_types table.
"""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from starlette_admin import DateTimeField, HasMany, IntegerField, StringField, TextAreaField
from starlette_admin.contrib.sqla import ModelView

from app.models.ai.template import AIPersona, AITemplate, AIType


class CountField(IntegerField):
    """Custom field for displaying count statistics with optional filters."""

    def __init__(
        self,
        count_model: Any,
        foreign_key_field: str,
        status_filter: int | None = None,
        is_reusable_filter: int | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        self.count_model = count_model
        self.foreign_key_field = foreign_key_field
        self.status_filter = status_filter
        self.is_reusable_filter = is_reusable_filter
        super().__init__(*args, **kwargs)

    async def parse_obj(self, request: Request, obj: Any) -> int:
        """Parse object to get count from database with filters."""
        session: AsyncSession = request.state.session
        stmt = (
            select(func.count())
            .select_from(self.count_model)
            .where(getattr(self.count_model, self.foreign_key_field) == obj.id)
        )

        # Apply status filter if specified
        if self.status_filter is not None:
            stmt = stmt.where(self.count_model.status == self.status_filter)

        # Apply is_reusable filter if specified
        if self.is_reusable_filter is not None:
            stmt = stmt.where(self.count_model.is_reusable == self.is_reusable_filter)

        result = await session.scalar(stmt)
        return result or 0


class AITypeView(ModelView):
    """CRUD view for ai_types entries."""

    exclude_fields_from_create = [
        "id",
        "created_at",
        "updated_at",
        "templates",
        "templates_single_use",
        "templates_reusable",
        "persona_total",
        "persona_active",
        "persona_active_reusable",
        "persona_active_single_use",
        "template_total",
        "template_active",
        "template_active_reusable",
        "template_active_single_use",
    ]
    exclude_fields_from_edit = [
        "id",
        "created_at",
        "updated_at",
        "templates",
        "templates_single_use",
        "templates_reusable",
        "persona_total",
        "persona_active",
        "persona_active_reusable",
        "persona_active_single_use",
        "template_total",
        "template_active",
        "template_active_reusable",
        "template_active_single_use",
    ]
    exclude_fields_from_list: Sequence[str] = [
        "templates",
        "templates_single_use",
        "templates_reusable",
        "persona_total",
        "persona_active_reusable",
        "persona_active_single_use",
        "template_total",
        "template_active_reusable",
        "template_active_single_use",
    ]

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["display_name"]
    sortable_fields = ["id", "display_name", "created_at", "updated_at"]

    fields = [
        StringField("id", label="ID", help_text="Internal AI type identifier"),
        StringField("display_name", label="Display Name", help_text="Admin display label"),
        TextAreaField("description", label="Description", help_text="Optional description"),
        # Statistics
        CountField(
            AIPersona,
            "type_id",
            name="persona_total",
            label="Personas (Total)",
            help_text="Total personas (all statuses)",
        ),
        CountField(
            AIPersona,
            "type_id",
            status_filter=1,
            name="persona_active",
            label="Personas (Active)",
            help_text="Active personas (status=1)",
        ),
        CountField(
            AIPersona,
            "type_id",
            status_filter=1,
            is_reusable_filter=1,
            name="persona_active_reusable",
            label="Personas (Active Reusable)",
            help_text="Active + Reusable personas",
        ),
        CountField(
            AIPersona,
            "type_id",
            status_filter=1,
            is_reusable_filter=0,
            name="persona_active_single_use",
            label="Personas (Active Single-use)",
            help_text="Active + Single-use personas",
        ),
        CountField(
            AITemplate,
            "type_id",
            name="template_total",
            label="Templates (Total)",
            help_text="Total templates (all statuses)",
        ),
        CountField(
            AITemplate,
            "type_id",
            status_filter=1,
            name="template_active",
            label="Templates (Active)",
            help_text="Active templates (status=1)",
        ),
        CountField(
            AITemplate,
            "type_id",
            status_filter=1,
            is_reusable_filter=1,
            name="template_active_reusable",
            label="Templates (Active Reusable)",
            help_text="Active + Reusable templates",
        ),
        CountField(
            AITemplate,
            "type_id",
            status_filter=1,
            is_reusable_filter=0,
            name="template_active_single_use",
            label="Templates (Active Single-use)",
            help_text="Active + Single-use templates",
        ),
        HasMany(
            "templates_single_use",
            identity="ai_template",
            label="Templates (Single-use)",
            help_text="Single-use templates linked to this AI type (sorted by priority)",
            exclude_from_list=True,
            exclude_from_create=True,
            exclude_from_edit=True,
        ),
        HasMany(
            "templates_reusable",
            identity="ai_template",
            label="Templates (Reusable)",
            help_text="Reusable templates linked to this AI type (sorted by priority)",
            exclude_from_list=True,
            exclude_from_create=True,
            exclude_from_edit=True,
        ),
        DateTimeField("created_at", label="Created At", help_text="Creation timestamp"),
        DateTimeField("updated_at", label="Updated At", help_text="Last update timestamp"),
    ]

    def can_delete(self, request: Request) -> bool:
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
