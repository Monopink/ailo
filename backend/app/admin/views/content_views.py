"""Content management views.

Provides admin tooling for app-facing content tables.
"""

from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from starlette.requests import Request
from starlette_admin import DateTimeField, EnumField, HasOne, StringField, TextAreaField
from starlette_admin.actions import link_row_action
from starlette_admin.contrib.sqla import ModelView
from starlette_admin.exceptions import FormValidationError

from app.admin.views.base import IntegerEnumField
from app.core.database import get_sessionmaker
from app.enums import (
    AdminOperationType,
    AppPageCategory,
    AppPageSourceType,
    AppPageStatus,
    ClientType,
    ExposureStrategy,
    LocaleCode,
    SquareCategory,
    SquareEntryStatus,
)
from app.models.ai.template import AIType
from app.models.content import AppPage, SquareTypeEntry
from app.services.pages import service as app_page_service
from app.utils.admin_logs import create_operation_log
from app.utils.logging import get_logger

logger = get_logger(__name__)


def _extract_relation_id(value: object) -> int | None:
    """Extract a relation primary key from a HasOne field value."""
    relation_id = getattr(value, "id", value)
    if relation_id is None:
        return None
    try:
        return int(cast(Any, relation_id))
    except (TypeError, ValueError):
        return None


class _AITypeDisplayNameField(StringField):
    """Computed field to show ai_type display_name for SquareTypeEntry."""

    def __init__(self, name: str = "ai_type_display_name", label: str = "AI Type Name") -> None:
        super().__init__(name=name, label=label)
        self.read_only = True
        self.searchable = False
        self.orderable = False

    async def parse_obj(self, request: Request, obj: Any) -> str:
        try:
            type_id = getattr(obj, "type_id", None)
            if type_id is None:
                return ""

            stmt = select(AIType.display_name).where(AIType.id == type_id)
            display_name = (await request.state.session.execute(stmt)).scalar_one_or_none()
            return str(display_name or "")
        except Exception:
            return ""


class SquareTypeEntryView(ModelView):
    """Manage square_type_entries records."""

    exclude_fields_from_create = [
        "id",
        "created_at",
        "updated_at",
        "ai_type_display_name",
    ]
    exclude_fields_from_edit = [
        "id",
        "created_at",
        "updated_at",
        "ai_type_display_name",
    ]
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
        DateTimeField("created_at", label="Created At", help_text="Creation timestamp"),
        DateTimeField("updated_at", label="Updated At", help_text="Last update timestamp"),
    ]

    async def before_create(self, request: Request, data: dict[str, Any], obj: Any) -> None:
        self._sync_ai_type(obj, data)

    async def before_edit(self, request: Request, data: dict[str, Any], obj: Any) -> None:
        self._sync_ai_type(obj, data)

    def _sync_ai_type(self, obj: Any, data: dict[str, Any]) -> None:
        """Keep `type_id` aligned with the submitted AI type relation."""
        if "ai_type" not in data:
            return
        obj.type_id = _extract_relation_id(data.get("ai_type"))

    def get_create_defaults(self, request: Request) -> dict[str, Any]:
        """Ensure new square entries default to active status."""
        return {"status": SquareEntryStatus.ACTIVE}

    async def create(self, request: Request, data: dict[str, Any]) -> Any:
        """Convert database integrity errors into field-level validation errors."""
        try:
            return await super().create(request, data)
        except IntegrityError as exc:
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
                ) from exc
            raise

    def can_delete(self, request: Request) -> bool:
        return False


class AppPageView(ModelView):
    """App page management view."""

    row_actions = ["view", "edit", "advanced_edit", "preview"]

    exclude_fields_from_create = [
        "id",
        "created_at",
        "updated_at",
    ]
    exclude_fields_from_edit = [
        "id",
        "created_at",
        "updated_at",
    ]

    fields_default_sort = [("updated_at", True)]
    searchable_fields = ["page_key", "title", "client_type", "locale"]
    sortable_fields = [
        "id",
        "page_key",
        "client_type",
        "locale",
        "page_category",
        "source_type",
        "status",
        "updated_at",
    ]

    fields = [
        StringField("id", label="ID", help_text="Page ID"),
        StringField(
            "page_key",
            label="Page Key",
            help_text="Lowercase key, letters/numbers/underscore only",
            required=True,
        ),
        EnumField(
            "client_type",
            choices=[(item.value, item.value) for item in ClientType],
            label="Client Type",
            help_text="Derived from X-Client, fixed to mini-program",
            required=True,
        ),
        EnumField(
            "locale",
            choices=[(item.value, item.value) for item in LocaleCode],
            label="Locale",
            help_text="Current fixed value: zh-CN",
            required=True,
        ),
        IntegerEnumField(
            "page_category",
            enum=AppPageCategory,
            label="Page Category",
            help_text="1=policy, 2=info",
            required=True,
        ),
        IntegerEnumField(
            "source_type",
            enum=AppPageSourceType,
            label="Source Type",
            help_text="1=markdown, 2=html",
            required=True,
        ),
        StringField(
            "title",
            label="Title",
            help_text="Page title shown to users",
            required=False,
        ),
        TextAreaField(
            "content_md",
            label="Markdown Source",
            help_text="Markdown content, can be empty",
            required=False,
        ),
        TextAreaField(
            "content_html",
            label="HTML Content",
            help_text="Sanitized before save; markdown mode auto-overwrites this field",
            required=False,
        ),
        IntegerEnumField(
            "status",
            enum=AppPageStatus,
            label="Status",
            help_text="Only ACTIVE pages are returned by user APIs",
            required=True,
        ),
        DateTimeField("created_at", label="Created At", help_text="Creation timestamp"),
        DateTimeField("updated_at", label="Updated At", help_text="Last update timestamp"),
    ]

    def is_active(self, request: Request) -> bool:
        """Keep menu active for custom app page views."""
        if request.path_params.get("identity", None) == self.identity:
            return True
        path = request.scope["path"]
        return f"/{self.identity}/advanced-edit/" in path or f"/{self.identity}/preview/" in path

    def can_delete(self, request: Request) -> bool:
        return False

    @link_row_action(
        name="advanced_edit",
        text="Advanced Edit",
        icon_class="fas fa-cogs",
    )
    def advanced_edit_row_action(self, _request: Request, pk: Any) -> str:
        """Link to app page advanced edit page."""
        return f"/qiao-dash/app_page/advanced-edit/{pk}"

    @link_row_action(
        name="preview",
        text="Preview",
        icon_class="fas fa-file-alt",
    )
    def preview_row_action(self, _request: Request, pk: Any) -> str:
        """Link to app page preview page."""
        return f"/qiao-dash/app_page/preview/{pk}"

    def get_create_defaults(self, request: Request) -> dict[str, Any]:
        return {
            "locale": app_page_service.DEFAULT_PAGE_LOCALE,
            "status": AppPageStatus.ACTIVE,
            "client_type": app_page_service.DEFAULT_CLIENT_TYPE,
            "page_category": AppPageCategory.INFO,
            "source_type": AppPageSourceType.MARKDOWN,
        }

    async def before_create(self, request: Request, data: dict[str, Any], obj: Any) -> None:
        self._prepare_document(obj)

    async def before_edit(self, request: Request, data: dict[str, Any], obj: Any) -> None:
        self._prepare_document(obj)

    async def create(self, request: Request, data: dict[str, Any]) -> Any:
        """Persist app page and write an admin audit log entry."""
        try:
            page = await super().create(request, data)
        except IntegrityError as exc:
            self._raise_app_page_integrity_error(exc)
            raise
        await self._log_admin_operation(
            request=request,
            page=page,
            operation_type=AdminOperationType.CREATE,
            operation_desc="Created app page via admin list form",
        )
        return page

    async def edit(self, request: Request, pk: Any, data: dict[str, Any]) -> Any:
        """Persist app page edits and write an admin audit log entry."""
        try:
            page = await super().edit(request, pk, data)
        except IntegrityError as exc:
            self._raise_app_page_integrity_error(exc)
            raise
        await self._log_admin_operation(
            request=request,
            page=page,
            operation_type=AdminOperationType.UPDATE,
            operation_desc="Updated app page via admin list form",
        )
        return page

    def _prepare_document(self, obj: Any) -> None:
        try:
            obj.page_key = app_page_service.normalize_page_key(str(getattr(obj, "page_key", "")))
        except app_page_service.AppPageValidationError as exc:
            raise FormValidationError({"page_key": "Invalid page_key format"}) from exc

        try:
            obj.client_type = app_page_service.normalize_client_type(
                str(getattr(obj, "client_type", ""))
            )
        except app_page_service.AppPageValidationError as exc:
            raise FormValidationError({"client_type": "Invalid client_type format"}) from exc

        try:
            obj.locale = app_page_service.normalize_locale(str(getattr(obj, "locale", "")))
        except app_page_service.AppPageValidationError as exc:
            raise FormValidationError({"locale": "Only zh-CN is supported"}) from exc

        try:
            obj.page_category = app_page_service.normalize_page_category(
                getattr(obj, "page_category", "")
            )
        except app_page_service.AppPageValidationError as exc:
            raise FormValidationError({"page_category": "Invalid page_category"}) from exc

        try:
            obj.source_type = app_page_service.normalize_source_type(
                getattr(obj, "source_type", "")
            )
        except app_page_service.AppPageValidationError as exc:
            raise FormValidationError({"source_type": "Invalid source_type"}) from exc

        raw_title = getattr(obj, "title", "")
        obj.title = str(raw_title or "").strip()

        raw_content_md = getattr(obj, "content_md", "")
        content_md = str(raw_content_md or "")
        raw_content_html = getattr(obj, "content_html", "")
        content_html = str(raw_content_html or "")
        try:
            obj.content_md, obj.content_html = app_page_service.resolve_page_contents(
                source_type=obj.source_type,
                content_md=content_md,
                content_html=content_html,
            )
        except app_page_service.AppPageValidationError as exc:
            raise FormValidationError({"content_md": "Invalid content"}) from exc

    @staticmethod
    def _raise_app_page_integrity_error(exc: IntegrityError) -> None:
        """Convert app_pages uniqueness conflicts into form-level errors."""
        error_msg = str(exc.orig) if hasattr(exc, "orig") else str(exc)
        if (
            "uq_app_pages_page_client_locale" in error_msg
            or "(page_key, client_type, locale)" in error_msg
        ):
            conflict = "A page with the same page_key, client_type, and locale already exists"
            raise FormValidationError(
                {
                    "page_key": conflict,
                    "client_type": conflict,
                    "locale": conflict,
                }
            ) from exc

    def _resolve_admin_user_id(self, request: Request) -> int | None:
        """Resolve admin user id from Starlette-Admin session payload."""
        if not hasattr(request, "session"):
            return None
        admin_user = request.session.get("admin_user")
        if not isinstance(admin_user, dict):
            return None
        raw_id = admin_user.get("id")
        if raw_id is None or not isinstance(raw_id, str | int):
            return None
        try:
            return int(raw_id)
        except (TypeError, ValueError):
            return None

    async def _log_admin_operation(
        self,
        request: Request,
        page: Any,
        operation_type: AdminOperationType,
        operation_desc: str,
    ) -> None:
        """Record app page write operations into admin_operation_logs."""
        admin_user_id = self._resolve_admin_user_id(request)
        if admin_user_id is None:
            logger.warning(
                "app_page_audit_skip_missing_admin_user",
                operation_type=operation_type.name,
            )
            return

        resource_id = getattr(page, "id", None)
        resource_name = str(getattr(page, "page_key", "") or "")
        session_factory = get_sessionmaker()
        async with session_factory() as db:
            await create_operation_log(
                db=db,
                admin_user_id=admin_user_id,
                operation_type=operation_type.value,
                resource_type="app_page",
                resource_id=str(resource_id) if resource_id is not None else None,
                resource_name=resource_name or None,
                operation_desc=operation_desc,
                request=request,
            )


app_page_view = AppPageView(AppPage, name="App Pages", icon="fa fa-book", identity="app_page")
square_type_entry_view = SquareTypeEntryView(
    SquareTypeEntry,
    name="Square Entries",
    label="Square Entries",
    icon="fa fa-square",
    identity="square_type_entry",
)

CONTENT_MODEL_VIEWS = [
    app_page_view,
    square_type_entry_view,
]
