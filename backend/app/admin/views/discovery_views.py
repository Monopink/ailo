"""
Discovery management views.

Provides admin tooling for Square exposure tables.
"""

from typing import Any, Dict

from admin.fields import LocalDateTimeField
from admin.views.base import IntegerEnumField
from enums import ExposureStrategy, SquareCategory, SquareEntryStatus
from models.discovery import SquareTypeEntry
from sqlalchemy.exc import IntegrityError
from starlette.requests import Request
from starlette_admin import HasOne, StringField
from starlette_admin.contrib.sqla import ModelView
from starlette_admin.exceptions import FormValidationError


class _AITypeDisplayNameField(StringField):
    """Computed field to show ai_type display_name for SquareTypeEntry."""

    def __init__(self, name: str = "ai_type_display_name", label: str = "AI Type Name"):
        super().__init__(name=name, label=label)
        self.read_only = True
        self.searchable = False
        self.orderable = False

    async def parse_obj(self, request, obj):  # type: ignore[override]
        try:
            if hasattr(obj, "ai_type") and obj.ai_type is not None:
                return str(getattr(obj.ai_type, "display_name", "") or "")
            return ""
        except Exception:
            return ""


class SquareTypeEntryView(ModelView):
    """Manage square_type_entries records."""

    exclude_fields_from_create = ["id", "created_at", "updated_at", "ai_type_display_name"]
    exclude_fields_from_edit = ["id", "created_at", "updated_at", "ai_type_display_name"]
    exclude_fields_from_list = []

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["square_category"]
    sortable_fields = [
        "id",
        "square_category",
        "type_id",
        "status",
        "created_at",
        "updated_at",
    ]

    fields = [
        StringField("id", label="ID", help_text="Square entry ID"),
        IntegerEnumField(
            "square_category",
            enum=SquareCategory,
            label="Square Category",
            required=True,
            help_text="Built-in Square category (friend/love/talk/...)",
        ),
        _AITypeDisplayNameField(),
        HasOne(
            "ai_type",
            identity="ai_type",
            label="AI Type",
            help_text="AI type that should appear in this discovery slot",
            required=True,
        ),
        IntegerEnumField(
            "exposure_strategy",
            enum=ExposureStrategy,
            required=True,
            label="Exposure Strategy",
            help_text="Selection strategy hint (currently only Random=1)",
        ),
        IntegerEnumField(
            "status",
            enum=SquareEntryStatus,
            label="Status",
            help_text="Only active entries are surfaced to clients",
            required=True,
        ),
        LocalDateTimeField("created_at", label="Created At", help_text="Creation timestamp"),
        LocalDateTimeField("updated_at", label="Updated At", help_text="Last update timestamp"),
    ]

    async def before_create(self, request: Request, data, obj):
        self._sync_ai_type(obj)

    async def before_edit(self, request: Request, data, obj):
        self._sync_ai_type(obj)

    def _sync_ai_type(self, obj: Any) -> None:
        """Keep `type_id` aligned with the selected AI type relation."""
        selected = getattr(obj, "ai_type", None)
        if selected is None:
            return

        # Admin sends HasOne selections as primary key strings; fall back to object.id
        type_id_candidate = None
        if isinstance(selected, dict):
            type_id_candidate = selected.get("id") or selected.get("value")
        elif hasattr(selected, "id"):
            type_id_candidate = getattr(selected, "id")
        else:
            type_id_candidate = selected

        if type_id_candidate is None:
            return

        try:
            obj.type_id = int(type_id_candidate)
        except (TypeError, ValueError):
            obj.type_id = type_id_candidate

    def get_create_defaults(self, request: Request) -> dict[str, Any]:
        """Ensure new square entries default to active status."""
        return {"status": SquareEntryStatus.ACTIVE}

    async def create(self, request: Request, data: Dict[str, Any]) -> Any:
        """Override create to catch database integrity errors and convert to friendly messages."""
        try:
            return await super().create(request, data)
        except IntegrityError as exc:
            # Check if it's a unique constraint violation
            error_msg = str(exc.orig) if hasattr(exc, "orig") else str(exc)
            if (
                "square_type_entries_square_category_type_id_key" in error_msg
                or "duplicate key" in error_msg.lower()
            ):
                conflict = "An entry with this category and AI type already exists"
                raise FormValidationError(
                    {
                        "square_category": conflict,
                        "ai_type": conflict,
                        "type_id": conflict,
                    }
                )
            # Re-raise other integrity errors
            raise

    def can_delete(self, request: Request) -> bool:  # type: ignore[override]
        return False


square_type_entry_view = SquareTypeEntryView(
    SquareTypeEntry,
    name="Square Entries",
    label="Square Entries",
    icon="fa fa-square",
    identity="square_type_entry",
)

DISCOVERY_MODEL_VIEWS = [
    square_type_entry_view,
]
