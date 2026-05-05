"""AI Template admin views.

This module contains Starlette-Admin views for AI instance configuration and persona inventory.
"""

from collections.abc import MutableMapping, Sequence
from typing import Any, ClassVar, cast

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from starlette_admin import (
    DateTimeField,
    HasOne,
    ImageField,
    IntegerField,
    JSONField,
    StringField,
    TextAreaField,
)
from starlette_admin._types import RequestAction
from starlette_admin.actions import link_row_action
from starlette_admin.contrib.sqla import ModelView
from starlette_admin.exceptions import FormValidationError
from starlette_admin.fields import BaseField, RelationField

from app.admin.views.base import IntegerEnumField
from app.enums import (
    AIPersonaStatus,
    AITemplateStatus,
    Gender,
    ProfileOwnerType,
    ReusableStatus,
)
from app.models.ai.memory import AITemplateMemory
from app.models.ai.personality import AIPersonality
from app.models.ai.style import AIDimension, AIStyleDimension
from app.models.ai.template import AIPersona, AITemplate
from app.models.base import generate_qiao_id
from app.models.profile import Profile
from app.services.ai.response_schema import validate_style_personality_contract
from app.services.profile.avatar import get_avatar_url
from app.services.profile.integrity import ensure_persona_profile
from app.services.security.username import (
    USERNAME_HELP_TEXT,
    UsernameValidationConfigError,
    validate_username_or_error,
)
from app.utils.contact_tags import (
    TAG_MAX_COUNT,
    TAG_MAX_LENGTH,
    TAG_MAX_TOTAL_LENGTH,
    compute_total_length,
    normalize_tags,
)
from app.utils.logging import get_logger
from app.utils.text_limits import CONTACT_REMARK_RULE, validate_text_limit

FormData = MutableMapping[str, object]
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
        obj.type_id = _extract_relation_id(_data.get("ai_type"))
        obj.style_id = _extract_relation_id(_data.get("style"))
        obj.personality_id = _extract_relation_id(_data.get("personality"))
        obj.llm_config_id = _extract_relation_id(_data.get("llm_config"))

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

        contract_error = await self._validate_template_contract(
            _request.state.session,
            style_id=getattr(obj, "style_id", None),
            personality_id=getattr(obj, "personality_id", None),
        )
        if contract_error is not None:
            raise FormValidationError({"personality": contract_error})

    async def before_edit(self, _request: Request, _data: FormData, obj: AITemplate) -> None:
        """Auto-fill foreign keys before editing template."""
        if "ai_type" in _data:
            obj.type_id = _extract_relation_id(_data.get("ai_type"))
        if "style" in _data:
            obj.style_id = _extract_relation_id(_data.get("style"))
        if "personality" in _data:
            obj.personality_id = _extract_relation_id(_data.get("personality"))
        if "llm_config" in _data:
            obj.llm_config_id = _extract_relation_id(_data.get("llm_config"))

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

        contract_error = await self._validate_template_contract(
            _request.state.session,
            style_id=getattr(obj, "style_id", None),
            personality_id=getattr(obj, "personality_id", None),
        )
        if contract_error is not None:
            raise FormValidationError({"personality": contract_error})

    @staticmethod
    async def _validate_template_contract(
        session: AsyncSession,
        *,
        style_id: int | None,
        personality_id: int | None,
    ) -> str | None:
        """Validate style/personality score-schema contract before save."""
        if style_id is None or personality_id is None:
            return None

        style_result = await session.execute(
            select(AIDimension.name)
            .join(AIStyleDimension, AIStyleDimension.dimension_id == AIDimension.id)
            .where(AIStyleDimension.style_id == style_id)
            .order_by(AIDimension.name)
        )
        style_dimension_names = [row[0] for row in style_result.all() if isinstance(row[0], str)]
        if not style_dimension_names:
            return "Selected style has no dimensions"

        personality_result = await session.execute(
            select(AIPersonality.json_schema).where(AIPersonality.id == personality_id)
        )
        personality_schema = personality_result.scalar_one_or_none()
        if personality_schema is None:
            return "Selected personality not found"

        try:
            validate_style_personality_contract(style_dimension_names, personality_schema)
        except (TypeError, ValueError) as exc:
            return f"Style/personality contract mismatch: {exc!s}"
        return None

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
            help_text=("选择优先级：数字越小越优先；同可复用分组内同优先级随机。"),
            required=True,
        ),
        IntegerEnumField(
            "status",
            enum=AITemplateStatus,
            label="Status",
            help_text="Active templates can be used",
            required=True,
        ),
        DateTimeField("created_at", label="Created At", help_text="Creation time"),
        DateTimeField("updated_at", label="Updated At", help_text="Last update time"),
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


class _PersonaAvatarPreviewField(ImageField):
    """Computed field showing Profile avatar for an AIPersona."""

    def __init__(
        self, name: str = "avatar_preview", label: str = "Avatar", **kwargs: object
    ) -> None:
        super().__init__(name=name, label=label, **kwargs)
        self.read_only = True
        self.searchable = False
        self.orderable = False

    async def parse_obj(self, request: Request, obj: AIPersona) -> dict[str, str] | None:
        try:
            stmt = select(Profile).where(
                Profile.owner_qiao_id == obj.qiao_id,
                Profile.owner_type == int(ProfileOwnerType.AI_PERSONA),
            )
            profile = (await request.state.session.execute(stmt)).scalar_one_or_none()
            avatar_url = await get_avatar_url(profile)
        except Exception:
            return None
        return {"url": avatar_url}


class AIPersonaView(ModelView):
    """AI persona inventory view."""

    exclude_fields_from_create: ClassVar[list[str]] = [
        "id",
        "avatar_preview",
        "type_id",
        "profile_nickname",
        "profile_gender",
        "created_at",
        "updated_at",
    ]
    exclude_fields_from_edit: ClassVar[list[str]] = [
        "id",
        "avatar_preview",
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

        persona = await super().create(request, data)
        try:
            await ensure_persona_profile(
                request.state.session,
                persona_id=getattr(persona, "id", None),
                persona_qiao_id=getattr(persona, "qiao_id", None),
                source="admin_create_persona",
                commit=True,
            )
        except Exception as exc:
            persona_id = getattr(persona, "id", None)
            logger.error(
                "admin_persona_profile_init_failed",
                persona_id=persona_id,
                persona_qiao_id=getattr(persona, "qiao_id", None),
                error=str(exc),
            )
            if isinstance(persona_id, int):
                try:
                    await request.state.session.execute(
                        delete(AIPersona).where(AIPersona.id == persona_id)
                    )
                    await request.state.session.commit()
                except Exception as cleanup_exc:
                    await request.state.session.rollback()
                    logger.error(
                        "admin_persona_profile_init_cleanup_failed",
                        persona_id=persona_id,
                        error=str(cleanup_exc),
                    )
            raise FormValidationError(
                {"profile_nickname": "Persona profile initialization failed"}
            ) from exc
        return persona

    def _sync_ai_type(self, obj: AIPersona, data: FormData) -> None:
        if "ai_type" not in data:
            return
        obj.type_id = _extract_relation_id(data.get("ai_type"))

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
        _PersonaAvatarPreviewField(
            "avatar_preview",
            label="Avatar",
            help_text="Current avatar preview",
        ),
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
            required=False,
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
        JSONField(
            "tags",
            label="Preset Tags",
            help_text='JSON array of strings (e.g. ["朋友","聊天"]). Used to populate contacts.tags on add.',
        ),
        TextAreaField(
            "remark",
            label="Preset Remark",
            help_text="Used to populate contacts.remark on add.",
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
        DateTimeField("created_at", label="Created At", help_text="Creation timestamp"),
        DateTimeField("updated_at", label="Updated At", help_text="Last update timestamp"),
    ]
    row_actions: ClassVar[list[str]] = ["view", "profile", "edit"]

    @link_row_action(
        name="profile",
        text="Profile",
        icon_class="fa fa-id-card",
    )
    def profile_detail_action(self, _request: Request, pk: int | str) -> str:
        """Open owner profile detail page."""
        return f"/admin-api/profile/owner-link/ai_persona/{pk}"

    async def before_create(self, request: Request, _data: FormData, obj: AIPersona) -> None:
        """Ensure ai_type is set before creating a persona."""
        self._sync_ai_type(obj, _data)
        errors = {}
        if not hasattr(obj, "type_id") or obj.type_id is None:
            errors["ai_type"] = "AI Type is required"
        username = getattr(obj, "username", None)
        normalized_username: str | None = None
        if username is None:
            obj.username = None
        elif isinstance(username, str):
            normalized_username = username.strip()
            if not normalized_username:
                obj.username = None
                normalized_username = None
            else:
                obj.username = normalized_username
        else:
            errors["username"] = "Username must be a string"

        if normalized_username is not None:
            try:
                username_error = await validate_username_or_error(
                    request.state.session, normalized_username
                )
            except UsernameValidationConfigError as exc:
                errors["username"] = str(exc)
            else:
                if username_error is not None:
                    errors["username"] = username_error
                else:
                    exists_stmt = select(AIPersona.id).where(
                        func.lower(AIPersona.username) == normalized_username.lower()
                    )
                    with request.state.session.no_autoflush:
                        exists_result = await request.state.session.execute(exists_stmt)
                    if exists_result.scalar_one_or_none() is not None:
                        errors["username"] = "Username already exists"

        raw_tags = getattr(obj, "tags", None)
        if raw_tags is not None:
            if (not isinstance(raw_tags, list)) or any(
                not isinstance(item, str) for item in raw_tags
            ):
                errors["tags"] = "Preset Tags must be a JSON array of strings"
            else:
                normalized = normalize_tags(raw_tags) or []
                if any(len(tag) > TAG_MAX_LENGTH for tag in normalized):
                    errors["tags"] = f"Each tag must be at most {TAG_MAX_LENGTH} characters"
                elif len(normalized) > TAG_MAX_COUNT:
                    errors["tags"] = f"Tag count must be at most {TAG_MAX_COUNT}"
                elif compute_total_length(normalized) > TAG_MAX_TOTAL_LENGTH:
                    errors["tags"] = f"Total tags length must be at most {TAG_MAX_TOTAL_LENGTH}"
                else:
                    obj.tags = normalized

        raw_remark = getattr(obj, "remark", None)
        if isinstance(raw_remark, str) and raw_remark.strip() == "":
            obj.remark = None
            raw_remark = None
        if raw_remark is not None:
            if not isinstance(raw_remark, str):
                errors["remark"] = "Preset Remark must be a string"
            else:
                remark_error = validate_text_limit(raw_remark, CONTACT_REMARK_RULE)
                if remark_error is not None:
                    errors["remark"] = remark_error
        if errors:
            raise FormValidationError(errors)

    async def before_edit(self, request: Request, _data: FormData, obj: AIPersona) -> None:
        """Keep ai_type synchronized when editing."""
        self._sync_ai_type(obj, _data)
        errors = {}
        if not hasattr(obj, "type_id") or obj.type_id is None:
            errors["ai_type"] = "AI Type is required"
        username = getattr(obj, "username", None)
        normalized_username: str | None = None
        if username is None:
            obj.username = None
        elif isinstance(username, str):
            normalized_username = username.strip()
            if not normalized_username:
                obj.username = None
                normalized_username = None
            else:
                obj.username = normalized_username
        else:
            errors["username"] = "Username must be a string"

        if normalized_username is not None:
            try:
                username_error = await validate_username_or_error(
                    request.state.session, normalized_username
                )
            except UsernameValidationConfigError as exc:
                errors["username"] = str(exc)
            else:
                if username_error is not None:
                    errors["username"] = username_error
                else:
                    exists_stmt = select(AIPersona.id).where(
                        func.lower(AIPersona.username) == normalized_username.lower(),
                        AIPersona.id != obj.id,
                    )
                    with request.state.session.no_autoflush:
                        exists_result = await request.state.session.execute(exists_stmt)
                    if exists_result.scalar_one_or_none() is not None:
                        errors["username"] = "Username already exists"

        raw_tags = getattr(obj, "tags", None)
        if raw_tags is not None:
            if (not isinstance(raw_tags, list)) or any(
                not isinstance(item, str) for item in raw_tags
            ):
                errors["tags"] = "Preset Tags must be a JSON array of strings"
            else:
                normalized = normalize_tags(raw_tags) or []
                if any(len(tag) > TAG_MAX_LENGTH for tag in normalized):
                    errors["tags"] = f"Each tag must be at most {TAG_MAX_LENGTH} characters"
                elif len(normalized) > TAG_MAX_COUNT:
                    errors["tags"] = f"Tag count must be at most {TAG_MAX_COUNT}"
                elif compute_total_length(normalized) > TAG_MAX_TOTAL_LENGTH:
                    errors["tags"] = f"Total tags length must be at most {TAG_MAX_TOTAL_LENGTH}"
                else:
                    obj.tags = normalized

        raw_remark = getattr(obj, "remark", None)
        if isinstance(raw_remark, str) and raw_remark.strip() == "":
            obj.remark = None
            raw_remark = None
        if raw_remark is not None:
            if not isinstance(raw_remark, str):
                errors["remark"] = "Preset Remark must be a string"
            else:
                remark_error = validate_text_limit(raw_remark, CONTACT_REMARK_RULE)
                if remark_error is not None:
                    errors["remark"] = remark_error
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
    sortable_fields: ClassVar[list[str]] = [
        "template_id",
        "display_order",
        "importance",
    ]

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
        DateTimeField("created_at", label="Created At"),
        DateTimeField("updated_at", label="Updated At"),
    ]

    async def before_create(
        self, _request: Request, _data: FormData, obj: AITemplateMemory
    ) -> None:
        """Ensure template_id is synced from submitted relation field."""
        obj.template_id = _extract_relation_id(_data.get("template"))

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
        if "template" in _data:
            obj.template_id = _extract_relation_id(_data.get("template"))


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
