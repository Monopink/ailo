"""AI Template admin views.

This module contains Starlette-Admin views for AI instance configuration and persona inventory.
"""

from collections.abc import MutableMapping, Sequence
from typing import ClassVar

from sqlalchemy import func, select
from starlette.requests import Request
from starlette_admin import HasOne, IntegerField, JSONField, StringField, TextAreaField
from starlette_admin._types import RequestAction
from starlette_admin.actions import link_row_action
from starlette_admin.contrib.sqla import ModelView
from starlette_admin.exceptions import FormValidationError
from starlette_admin.fields import BaseField, RelationField

from app.admin.fields import LocalDateTimeField
from app.admin.views.base import IntegerEnumField
from app.enums import AIPersonaStatus, AITemplateStatus, Gender, ProfileOwnerType, ReusableStatus
from app.models.ai.memory import AITemplateMemory
from app.models.ai.template import AIPersona, AITemplate
from app.models.base import generate_qiao_id
from app.models.profile import Profile
from app.services.security.username import (
    USERNAME_HELP_TEXT,
    UsernameValidationConfigError,
    validate_username_or_error,
)

FormData = MutableMapping[str, object]


class AITemplateView(ModelView):
    """Enhanced AI Template view with proper field configuration."""

    exclude_fields_from_create: ClassVar[list[str]] = [
        "id",
        "created_at",
        "updated_at",
        "type_id",  # Auto-filled from ai_type relationship
    ]
    exclude_fields_from_edit: ClassVar[list[str]] = [
        "id",
        "created_at",
        "updated_at",
        "type_id",  # Auto-filled from ai_type relationship
    ]
    exclude_fields_from_list: ClassVar[list[str]] = [
        "type_id",  # Redundant with ai_type relationship field
    ]
    exclude_fields_from_detail: ClassVar[list[str]] = [
        "type_id",
    ]

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

    async def before_create(self, _request: Request, _data: FormData, obj: AITemplate) -> None:
        """Auto-fill foreign keys before creating template."""
        # Auto-fill foreign keys from HasOne relationships
        if hasattr(obj, "ai_type") and obj.ai_type is not None:
            obj.type_id = obj.ai_type.id
        if hasattr(obj, "style") and obj.style is not None:
            obj.style_id = obj.style.id
        if hasattr(obj, "personality") and obj.personality is not None:
            obj.personality_id = obj.personality.id
        if hasattr(obj, "llm_config") and obj.llm_config is not None:
            obj.llm_config_id = obj.llm_config.id
        else:
            obj.llm_config_id = None

        if hasattr(obj, "timezone") and (obj.timezone is None or obj.timezone == ""):
            obj.timezone = "Asia/Shanghai"

        # Validate required foreign keys
        errors = {}
        if not hasattr(obj, "type_id") or obj.type_id is None:
            errors["ai_type"] = "AI Type is required"
        if not hasattr(obj, "style_id") or obj.style_id is None:
            errors["style"] = "AI Style is required"
        if not hasattr(obj, "personality_id") or obj.personality_id is None:
            errors["personality"] = "AI Personality is required"

        if errors:
            raise FormValidationError(errors)

    async def before_edit(self, _request: Request, _data: FormData, obj: AITemplate) -> None:
        """Auto-fill foreign keys before editing template."""
        if hasattr(obj, "ai_type") and obj.ai_type is not None:
            obj.type_id = obj.ai_type.id
        if hasattr(obj, "style") and obj.style is not None:
            obj.style_id = obj.style.id
        if hasattr(obj, "personality") and obj.personality is not None:
            obj.personality_id = obj.personality.id
        if hasattr(obj, "llm_config") and obj.llm_config is not None:
            obj.llm_config_id = obj.llm_config.id
        else:
            obj.llm_config_id = None

        if hasattr(obj, "timezone") and (obj.timezone is None or obj.timezone == ""):
            obj.timezone = "Asia/Shanghai"

        errors = {}
        if not hasattr(obj, "type_id") or obj.type_id is None:
            errors["ai_type"] = "AI Type is required"
        if not hasattr(obj, "style_id") or obj.style_id is None:
            errors["style"] = "AI Style is required"
        if not hasattr(obj, "personality_id") or obj.personality_id is None:
            errors["personality"] = "AI Personality is required"

        if errors:
            raise FormValidationError(errors)

    fields_default_sort: ClassVar[list[tuple[str, bool]]] = [("created_at", True)]
    searchable_fields: ClassVar[list[str]] = []
    sortable_fields: ClassVar[list[str]] = [
        "id",
        "type_id",
        "style_id",
        "personality_id",
        "priority",
        "status",
        "is_reusable",
        "profile_count",
        "created_at",
        "updated_at",
    ]

    fields: ClassVar[list[object]] = [
        StringField("id", label="ID", help_text="Internal AI template ID"),
        StringField(
            "display_name",
            label="Display Name",
            help_text="Human-readable name for this AI template",
        ),
        HasOne(
            "ai_type",
            identity="ai_type",
            label="AI Type",
            help_text="AI type grouping for this template",
            required=True,
        ),
        IntegerField(
            "type_id",
            label="AI Type ID",
            help_text="AI type grouped for this template",
        ),
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
        HasOne(
            "llm_config",
            identity="llm_config",
            label="LLM Config",
            help_text=(
                "Default llm_configs.id inherited by instances (leave blank for system default)"
            ),
            required=False,
        ),
        JSONField(
            "request_params",
            label="Request Parameters",
            help_text=(
                "LLM request parameters (temperature, max_tokens, etc.) - inherited by AI instances"
            ),
        ),
        "prompt_variables",
        StringField(
            "timezone",
            label="Timezone",
            help_text="IANA timezone for instantiated AI instances (e.g., Asia/Shanghai)",
            required=True,
        ),
        IntegerField(
            "typing_speed_wpm",
            label="Typing Speed (WPM)",
            help_text=(
                "Default typing speed that downstream AI instances inherit (words per minute)"
            ),
            required=True,
        ),
        JSONField(
            "position_mapping_config",
            label="Position Mapping Config",
            help_text="Raw JSON config per dimension",
        ),
        IntegerEnumField(
            "is_reusable",
            enum=ReusableStatus,
            label="Reusable",
            help_text="Whether this template can be used multiple times",
            required=True,
        ),
        IntegerField(
            "priority",
            label="Priority",
            help_text="Selection priority (lower number chosen first)",
            required=True,
        ),
        IntegerEnumField(
            "status",
            enum=AITemplateStatus,
            label="Status",
            help_text="Active templates can be used",
            required=True,
        ),
        LocalDateTimeField("created_at", label="Created At", help_text="Creation time"),
        LocalDateTimeField("updated_at", label="Updated At", help_text="Last update time"),
    ]

    def get_fields_list(
        self,
        request: Request,
        action: RequestAction = RequestAction.LIST,
    ) -> Sequence[BaseField]:
        """Skip relation fields that point to missing model attributes."""
        base_fields = super().get_fields_list(request, action)
        filtered_fields: list[BaseField] = []
        for field in base_fields:
            if isinstance(field, RelationField) and not hasattr(self.model, field.name):
                continue
            filtered_fields.append(field)
        return filtered_fields

    row_actions: ClassVar[list[str]] = ["view", "edit", "advanced_edit"]

    @link_row_action(
        name="advanced_edit",
        text="Advanced Edit",
        icon_class="fas fa-cogs",
    )
    def advanced_edit_row_action(self, _request: Request, pk: str) -> str:
        """Link to edit AI template JSON fields."""
        return f"/qiao-dash/ai_template/advanced-edit/{pk}"


class _PersonaRelatedStringField(StringField):
    """Computed field showing Profile attribute for an AIPersona."""

    def __init__(self, name: str, profile_attr: str, label: str) -> None:
        super().__init__(name=name, label=label)
        self._profile_attr = profile_attr
        self.read_only = True
        self.searchable = False
        self.orderable = False

    async def parse_obj(self, request: Request, obj: AIPersona) -> str | None:
        try:
            session = request.state.session
            if not getattr(obj, "qiao_id", None):
                return "(No Qiao ID)"

            # Query both the field value and check if profile exists
            stmt = select(Profile.id, getattr(Profile, self._profile_attr)).where(
                Profile.owner_qiao_id == obj.qiao_id,
                Profile.owner_type == ProfileOwnerType.AI_PERSONA,
            )
            result = await session.execute(stmt)
            row = result.first()

            # No profile record exists
            if row is None:
                return "(No Profile)"

            # Profile exists, check field value
            _profile_id, value = row
            if value is None:
                return None  # Framework will display as -null-
            if value == "":
                return "(Empty)"
            return str(value)
        except Exception:
            return "(Error)"


class _PersonaGenderField(StringField):
    """Computed field showing Profile.gender as enum name for an AIPersona."""

    def __init__(self, name: str = "profile_gender", label: str = "Profile Gender") -> None:
        super().__init__(name=name, label=label)
        self.read_only = True
        self.searchable = False
        self.orderable = False

    async def parse_obj(self, request: Request, obj: AIPersona) -> str | None:
        try:
            session = request.state.session
            if not getattr(obj, "qiao_id", None):
                return "(No Qiao ID)"

            # Query both profile existence and gender value
            stmt = select(Profile.id, Profile.gender).where(
                Profile.owner_qiao_id == obj.qiao_id,
                Profile.owner_type == ProfileOwnerType.AI_PERSONA,
            )
            result = await session.execute(stmt)
            row = result.first()

            # No profile record exists
            if row is None:
                return "(No Profile)"

            # Profile exists, check gender value
            _profile_id, value = row
            if value is None:
                return None  # Framework will display as -null-
            try:
                return str(Gender(int(value)).name)
            except Exception:
                return str(value)
        except Exception:
            return "(Error)"


class AIPersonaView(ModelView):
    """AI persona inventory view."""

    exclude_fields_from_create: ClassVar[list[str]] = [
        "id",
        "type_id",
        "profile_nickname",
        "profile_gender",
        "created_at",
        "updated_at",
    ]
    exclude_fields_from_edit: ClassVar[list[str]] = [
        "id",
        "type_id",
        "profile_nickname",
        "profile_gender",
        "created_at",
        "updated_at",
    ]

    async def create(self, request: Request, data: FormData) -> AIPersona:
        """Ensure qiao_id is generated if the admin did not override it."""
        if not data.get("qiao_id"):
            data["qiao_id"] = generate_qiao_id()

        # Set default is_reusable to REUSABLE if not provided
        if data.get("is_reusable") is None:
            data["is_reusable"] = ReusableStatus.REUSABLE

        return await super().create(request, data)

    def _sync_ai_type(self, obj: AIPersona) -> None:
        if hasattr(obj, "ai_type") and obj.ai_type is not None:
            obj.type_id = getattr(obj.ai_type, "id", obj.type_id)

    def can_delete(self, _request: Request) -> bool:
        return False

    fields_default_sort: ClassVar[list[tuple[str, bool]]] = [("created_at", True)]
    searchable_fields: ClassVar[list[str]] = ["qiao_id", "username"]
    sortable_fields: ClassVar[list[str]] = [
        "id",
        "qiao_id",
        "username",
        "is_reusable",
        "status",
        "created_at",
        "updated_at",
    ]

    fields: ClassVar[list[object]] = [
        StringField("id", label="ID", help_text="Internal persona identifier"),
        StringField(
            "qiao_id",
            label="Persona Qiao ID",
            help_text="System-generated qiao_id (editable if you need to override)",
        ),
        StringField(
            "username",
            label="Username",
            help_text=USERNAME_HELP_TEXT,
            minlength=5,
            maxlength=20,
            required=True,
        ),
        _PersonaRelatedStringField(
            "profile_nickname", profile_attr="nickname", label="Profile Nickname"
        ),
        _PersonaGenderField(),
        HasOne(
            "ai_type",
            identity="ai_type",
            label="AI Type",
            help_text="Select the AI type that owns this persona",
            required=True,
        ),
        IntegerEnumField(
            "is_reusable",
            enum=ReusableStatus,
            label="Reusable",
            help_text="1=reusable, 0=single-use",
            required=True,
        ),
        IntegerEnumField(
            "status",
            enum=AIPersonaStatus,
            label="Status",
            help_text="Persona lifecycle status",
            required=True,
        ),
        LocalDateTimeField("created_at", label="Created At", help_text="Creation timestamp"),
        LocalDateTimeField("updated_at", label="Updated At", help_text="Last update timestamp"),
    ]

    async def before_create(self, request: Request, _data: FormData, obj: AIPersona) -> None:
        """Ensure ai_type is set before creating a persona."""
        self._sync_ai_type(obj)
        errors = {}
        if not hasattr(obj, "type_id") or obj.type_id is None:
            errors["ai_type"] = "AI Type is required"
        username = getattr(obj, "username", None)
        if not isinstance(username, str) or not username:
            errors["username"] = "Username is required"
        else:
            try:
                username_error = await validate_username_or_error(request.state.session, username)
            except UsernameValidationConfigError as exc:
                errors["username"] = str(exc)
            else:
                if username_error is not None:
                    errors["username"] = username_error
                else:
                    exists_stmt = select(AIPersona.id).where(
                        func.lower(AIPersona.username) == username.lower()
                    )
                    exists_result = await request.state.session.execute(exists_stmt)
                    if exists_result.scalar_one_or_none() is not None:
                        errors["username"] = "Username already exists"
        if errors:
            raise FormValidationError(errors)

    async def before_edit(self, request: Request, _data: FormData, obj: AIPersona) -> None:
        """Keep ai_type synchronized when editing."""
        self._sync_ai_type(obj)
        errors = {}
        if not hasattr(obj, "type_id") or obj.type_id is None:
            errors["ai_type"] = "AI Type is required"
        username = getattr(obj, "username", None)
        if not isinstance(username, str) or not username:
            errors["username"] = "Username is required"
        else:
            try:
                username_error = await validate_username_or_error(request.state.session, username)
            except UsernameValidationConfigError as exc:
                errors["username"] = str(exc)
            else:
                if username_error is not None:
                    errors["username"] = username_error
                else:
                    exists_stmt = select(AIPersona.id).where(
                        func.lower(AIPersona.username) == username.lower(),
                        AIPersona.id != obj.id,
                    )
                    exists_result = await request.state.session.execute(exists_stmt)
                    if exists_result.scalar_one_or_none() is not None:
                        errors["username"] = "Username already exists"
        if errors:
            raise FormValidationError(errors)


class AITemplateMemoryView(ModelView):
    """Admin view for managing template seed memories."""

    label = "Template Memories"
    name = "Template Memories"

    exclude_fields_from_create: ClassVar[list[str]] = ["id", "created_at", "updated_at"]
    exclude_fields_from_edit: ClassVar[list[str]] = ["id", "created_at", "updated_at"]

    fields_default_sort: ClassVar[list[tuple[str, bool]]] = [("display_order", True)]
    searchable_fields: ClassVar[list[str]] = ["content"]
    sortable_fields: ClassVar[list[str]] = ["template_id", "display_order", "importance"]

    fields: ClassVar[list[object]] = [
        StringField("id", label="ID"),
        HasOne(
            "template",
            identity="ai_template",
            label="Template",
            help_text="Target template that will receive this memory",
            required=True,
        ),
        IntegerField(
            "template_id",
            label="Template ID",
            help_text="Populated automatically from the selected template",
            required=True,
        ),
        StringField(
            "memory_type",
            label="Memory Type",
            help_text="core 或 recent",
            required=True,
        ),
        IntegerField(
            "importance",
            label="Importance",
            help_text="1-10，控制寿命",
            required=True,
        ),
        IntegerField(
            "display_order",
            label="Display Order",
            help_text="复制顺序，越小越靠前",
            required=True,
        ),
        TextAreaField(
            "content",
            label="Content",
            help_text="记忆内容（建议一句话）",
            required=True,
        ),
        LocalDateTimeField("created_at", label="Created At"),
        LocalDateTimeField("updated_at", label="Updated At"),
    ]

    async def before_create(
        self, _request: Request, _data: FormData, obj: AITemplateMemory
    ) -> None:
        """Ensure template_id is synced from relationship."""
        if hasattr(obj, "template") and obj.template is not None:
            obj.template_id = obj.template.id

        errors = {}
        if not getattr(obj, "template_id", None):
            errors["template"] = "Template is required"
        if errors:
            raise FormValidationError(errors)

    async def before_edit(
        self,
        _request: Request,
        _data: FormData,
        obj: AITemplateMemory,
    ) -> None:
        """Ensure template relationship stays synchronized."""
        if hasattr(obj, "template") and obj.template is not None:
            obj.template_id = obj.template.id


# Create view instances
ai_template_view = AITemplateView(
    AITemplate,
    name="AI Templates",
    label="Templates",
    icon="fa fa-file-text",
    identity="ai_template",
)

ai_template_memory_view = AITemplateMemoryView(
    AITemplateMemory,
    name="Template Memories",
    label="Template Memories",
    icon="fa fa-bookmark",
    identity="ai_template_memory",
)

ai_persona_view = AIPersonaView(
    AIPersona,
    name="AI Persona Inventory",
    label="Personas",
    icon="fa fa-user-robot",
    identity="ai_persona",
)

# Export template views
AI_TEMPLATE_VIEWS = [
    ai_template_view,
    ai_template_memory_view,
    ai_persona_view,
]
