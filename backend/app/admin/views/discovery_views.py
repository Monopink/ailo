"""
Discovery management views.

Provides admin tooling for Square exposure tables.
"""

from typing import Any, Dict, Optional

from admin.fields import LocalDateTimeField
from admin.views.base import IntegerEnumField
from enums import ExposureStrategy, SquareCategory, SquareEntryStatus
from models.discovery import SquareTypeEntry
from services.discovery.validators import ensure_ai_type_has_active_persona
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from starlette.requests import Request
from starlette_admin import HasOne, StringField
from starlette_admin.contrib.sqla import ModelView
from starlette_admin.exceptions import FormValidationError


class SquareTypeEntryView(ModelView):
    """Manage square_type_entries records."""

    exclude_fields_from_create = ["id", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "created_at", "updated_at"]
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
        await self._validate_ai_type(request, obj.type_id)
        await self._ensure_unique_entry(request, obj.square_category, obj.type_id)

    async def before_edit(self, request: Request, data, obj):
        self._sync_ai_type(obj)
        await self._validate_ai_type(request, obj.type_id)
        await self._ensure_unique_entry(request, obj.square_category, obj.type_id, exclude_id=obj.id)

    def _sync_ai_type(self, obj: Any) -> None:
        """Keep `type_id` aligned with the selected AI type relation."""
        if hasattr(obj, "ai_type") and obj.ai_type is not None:
            obj.type_id = getattr(obj.ai_type, "id", obj.type_id)

    async def _ensure_unique_entry(
        self,
        request: Request,
        square_category: Optional[int],
        type_id: Optional[int],
        exclude_id: Optional[int] = None,
    ) -> None:
        """Prevent duplicate square entries for the same category+type."""
        if square_category is None or type_id is None:
            return

        session = request.state.session
        stmt = select(SquareTypeEntry).where(
            SquareTypeEntry.square_category == square_category,
            SquareTypeEntry.type_id == type_id,
        )
        if exclude_id:
            stmt = stmt.where(SquareTypeEntry.id != exclude_id)

        result = await session.execute(stmt)
        existing = result.scalars().first()
        if existing is not None:
            raise FormValidationError(
                {
                    "square_category": "An entry with this category and AI type already exists",
                    "type_id": "An entry with this category and AI type already exists",
                }
            )

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
                raise FormValidationError(
                    {
                        "square_category": "An entry with this category and AI type already exists",
                        "type_id": "An entry with this category and AI type already exists",
                    }
                )
            # Re-raise other integrity errors
            raise

    async def _validate_ai_type(self, request: Request, type_id: int) -> None:
        if not type_id:
            raise FormValidationError({"type_id": "AI Type is required"})
        session = request.state.session
        try:
            await ensure_ai_type_has_active_persona(session, type_id)
        except ValueError as exc:
            raise FormValidationError({"type_id": str(exc)})

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
