"""AI Instance admin views.

This module contains Starlette-Admin views for AI instance system.
"""

from collections.abc import MutableMapping
from typing import Any, ClassVar, cast

from sqlalchemy import select
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
from starlette_admin.actions import link_row_action
from starlette_admin.contrib.sqla import ModelView
from starlette_admin.exceptions import FormValidationError

from app.admin.views.base import IntegerEnumField
from app.enums import (
    AIInstanceCreator,
    AIInstanceMemoryStatus,
    AIInstanceStatus,
    Gender,
    ProfileOwnerType,
)
from app.models.ai import AIInstanceDimension
from app.models.ai.instance import AIInstance
from app.models.ai.memory import AIInstanceMemory
from app.models.ai.style import AIDimension, AIRelationship, AIStyleDimension
from app.models.ai.template import AITemplate
from app.models.profile import Profile
from app.services.ai.instance_creation import (
    ManualAIInstanceCreateError,
    create_manual_instance,
    validate_instance_contract,
)
from app.services.ai.utils.position_mapping import map_score_to_position
from app.services.profile.avatar import get_avatar_url
from app.utils.logging import get_logger

FormData = MutableMapping[str, object]
logger = get_logger(__name__)

POSITION_MIN = 0
POSITION_MAX = 1000
SCORE_MIN = 0
SCORE_MAX = 1000


def _extract_relation_id(value: object) -> int | None:
    """Extract a relation primary key from a HasOne field value."""
    relation_id = getattr(value, "id", value)
    if relation_id is None:
        return None
    try:
        return int(cast(Any, relation_id))
    except (TypeError, ValueError):
        return None


class _ProfileRelatedStringField(StringField):
    """Computed field showing Profile attribute for an AIInstance.

    It looks up profiles where owner_type=AI and owner_id=obj.id and returns
    the selected attribute as string.
    """

    def __init__(self, name: str, profile_attr: str, label: str) -> None:
        super().__init__(name=name, label=label)
        self._profile_attr = profile_attr
        self.read_only = True
        self.searchable = False
        self.orderable = False

    async def parse_obj(self, request: Request, obj: AIInstance) -> str | None:
        try:
            session = request.state.session
            if not getattr(obj, "qiao_id", None):
                return "(No Qiao ID)"

            # Query both the field value and check if profile exists
            stmt = select(Profile.id, getattr(Profile, self._profile_attr)).where(
                Profile.owner_qiao_id == obj.qiao_id,
                Profile.owner_type.in_([ProfileOwnerType.AI_INSTANCE, ProfileOwnerType.AI_PERSONA]),
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


class _ProfileGenderField(StringField):
    """Computed field showing Profile.gender as enum name for an AIInstance."""

    def __init__(self, name: str = "profile_gender", label: str = "Profile Gender") -> None:
        super().__init__(name=name, label=label)
        self.read_only = True
        self.searchable = False
        self.orderable = False

    async def parse_obj(self, request: Request, obj: AIInstance) -> str | None:
        try:
            session = request.state.session
            if not getattr(obj, "qiao_id", None):
                return "(No Qiao ID)"

            # Query both profile existence and gender value
            stmt = select(Profile.id, Profile.gender).where(
                Profile.owner_qiao_id == obj.qiao_id,
                Profile.owner_type.in_([ProfileOwnerType.AI_INSTANCE, ProfileOwnerType.AI_PERSONA]),
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


class _ProfileOwnerTypeField(StringField):
    """Computed field showing Profile.owner_type as enum name for an AIInstance."""

    def __init__(self, name: str = "profile_owner_type", label: str = "Profile Type") -> None:
        super().__init__(name=name, label=label)
        self.read_only = True
        self.searchable = False
        self.orderable = False

    async def parse_obj(self, request: Request, obj: AIInstance) -> str | None:
        try:
            session = request.state.session
            if not getattr(obj, "qiao_id", None):
                return "(No Qiao ID)"

            # Query both profile existence and owner_type value
            stmt = select(Profile.id, Profile.owner_type).where(
                Profile.owner_qiao_id == obj.qiao_id,
                Profile.owner_type.in_([ProfileOwnerType.AI_INSTANCE, ProfileOwnerType.AI_PERSONA]),
            )
            result = await session.execute(stmt)
            row = result.first()

            # No profile record exists
            if row is None:
                return "(No Profile)"

            # Profile exists, check owner_type value
            _profile_id, value = row
            if value is None:
                return None  # Framework will display as -null-
            try:
                return str(ProfileOwnerType(int(value)).name)
            except Exception:
                return str(value)
        except Exception:
            return "(Error)"


class _InstanceAvatarPreviewField(ImageField):
    """Computed field showing Profile avatar for an AIInstance."""

    def __init__(
        self, name: str = "avatar_preview", label: str = "Avatar", **kwargs: object
    ) -> None:
        super().__init__(name=name, label=label, **kwargs)
        self.read_only = True
        self.searchable = False
        self.orderable = False

    async def parse_obj(self, request: Request, obj: AIInstance) -> dict[str, str] | None:
        try:
            stmt = select(Profile).where(
                Profile.owner_qiao_id == obj.qiao_id,
                Profile.owner_type.in_(
                    [int(ProfileOwnerType.AI_INSTANCE), int(ProfileOwnerType.AI_PERSONA)]
                ),
            )
            profile = (await request.state.session.execute(stmt)).scalar_one_or_none()
            avatar_url = await get_avatar_url(profile)
        except Exception:
            return None
        return {"url": avatar_url}


class _RelationshipDisplayNameField(StringField):
    """Computed field to show relationship display_name for AIInstance."""

    def __init__(
        self,
        name: str = "relationship_display_name",
        label: str = "Relationship Name",
    ) -> None:
        super().__init__(name=name, label=label)
        self.read_only = True
        self.searchable = False
        self.orderable = False

    async def parse_obj(self, request: Request, obj: AIInstance) -> str | None:
        try:
            relationship_id = getattr(obj, "relationship_id", None)
            if relationship_id is None:
                return None

            stmt = select(AIRelationship.display_name).where(AIRelationship.id == relationship_id)
            display_name = (await request.state.session.execute(stmt)).scalar_one_or_none()
            if display_name is None:
                return None
            if display_name == "":
                return "(Empty)"
            return str(display_name)
        except Exception:
            return "(Error)"


class _TemplateDisplayNameField(StringField):
    """Computed field to show template display_name for AIInstance."""

    def __init__(
        self,
        name: str = "template_display_name",
        label: str = "Template Display Name",
    ) -> None:
        super().__init__(name=name, label=label)
        self.read_only = True
        self.searchable = False
        self.orderable = False

    async def parse_obj(self, request: Request, obj: AIInstance) -> str | None:
        try:
            template_id = getattr(obj, "template_id", None)
            if template_id is None:
                return None

            stmt = select(AITemplate.display_name).where(AITemplate.id == template_id)
            display_name = (await request.state.session.execute(stmt)).scalar_one_or_none()
            if display_name is None:
                return None
            if display_name == "":
                return "(Empty)"
            return str(display_name)
        except Exception:
            return "(Error)"


class _DimensionDisplayNameField(StringField):
    """Computed field to show dimension display_name for AIInstanceDimension."""

    def __init__(self, name: str = "dimension_display_name", label: str = "Dimension Name") -> None:
        super().__init__(name=name, label=label)
        self.read_only = True
        self.searchable = False
        self.orderable = False

    async def parse_obj(self, request: Request, obj: AIInstanceDimension) -> str:
        try:
            dimension_id = getattr(obj, "dimension_id", None)
            if dimension_id is None:
                return ""

            stmt = select(AIDimension.display_name).where(AIDimension.id == dimension_id)
            display_name = (await request.state.session.execute(stmt)).scalar_one_or_none()
            return str(display_name or "")
        except Exception:
            return ""


class AIInstanceView(ModelView):
    """Enhanced AI Instance view with proper field configuration."""

    exclude_fields_from_create: ClassVar[list[str]] = [
        "id",
        "avatar_preview",
        "user_id",
        "user_qiao_id",
        "created_by",
        "created_at",
        "updated_at",
        "profile_nickname",
        "profile_gender",
        "profile_owner_type",
        "template",
        "template_display_name",
        "relationship",
        "relationship_display_name",
    ]
    exclude_fields_from_edit: ClassVar[list[str]] = [
        "id",
        "avatar_preview",
        "qiao_id",
        "user",
        "user_id",
        "user_qiao_id",
        "created_by",
        "created_at",
        "updated_at",
        "profile_nickname",
        "profile_gender",
        "profile_owner_type",
        "template",
        "template_display_name",
        "relationship",
        "relationship_display_name",
    ]
    exclude_fields_from_list: ClassVar[list[str]] = [
        "creation_metadata",
    ]

    def is_active(self, request: Request) -> bool:
        """Check if current page is related to this model or its custom pages."""
        # Standard identity check for list/edit/detail pages
        if request.path_params.get("identity", None) == self.identity:
            return True

        # Check for advanced-edit page with exact identity match
        path = request.scope["path"]
        return f"/{self.identity}/advanced-edit/" in path

    def can_delete(self, _request: Request) -> bool:
        return False

    @staticmethod
    def _extract_relation_id(value: object) -> int | None:
        """Extract a relation primary key from a HasOne field value."""
        return _extract_relation_id(value)

    async def create(self, request: Request, data: FormData) -> AIInstance:
        """Create a manual AI instance through the application service."""
        try:
            return await create_manual_instance(
                request.state.session,
                user_id=self._extract_relation_id(data.get("user")),
                qiao_id=data.get("qiao_id"),
                style_id=self._extract_relation_id(data.get("style")),
                personality_id=self._extract_relation_id(data.get("personality")),
                relationship_id=self._extract_relation_id(data.get("relationship")),
                request_params=data.get("request_params"),
                llm_config_id=self._extract_relation_id(data.get("llm_config")),
                prompt_variables=data.get("prompt_variables"),
                relationship_counts=data.get("relationship_counts"),
                creation_metadata=data.get("creation_metadata"),
                status=cast(int | None, data.get("status")),
                typing_speed_wpm=data.get("typing_speed_wpm"),
                timezone=data.get("timezone"),
            )
        except ManualAIInstanceCreateError as exc:
            raise FormValidationError(exc.errors) from exc

    async def edit(self, request: Request, pk: str, data: FormData) -> AIInstance:
        """Override edit to handle data processing."""
        return await super().edit(request, pk, data)

    async def before_edit(self, _request: Request, _data: FormData, obj: AIInstance) -> None:
        """Auto-fill foreign keys before editing instance."""
        # Read relation IDs from submitted form data to avoid async lazy-loading on ORM relations.
        if "style" in _data:
            obj.style_id = self._extract_relation_id(_data.get("style"))
        if "personality" in _data:
            obj.personality_id = self._extract_relation_id(_data.get("personality"))
        if "relationship" in _data:
            obj.relationship_id = self._extract_relation_id(_data.get("relationship"))
        if "llm_config" in _data:
            obj.llm_config_id = self._extract_relation_id(_data.get("llm_config"))
        if "persona" in _data:
            obj.persona_id = self._extract_relation_id(_data.get("persona"))

        if hasattr(obj, "timezone") and (obj.timezone is None or obj.timezone == ""):
            obj.timezone = "Asia/Shanghai"

        if not hasattr(obj, "creation_metadata") or obj.creation_metadata is None:
            obj.creation_metadata = {}
        if isinstance(obj.creation_metadata, dict):
            source = obj.creation_metadata.get("source")
            if source == "admin_manual":
                obj.persona_id = None

        # Validate required foreign keys
        errors = {}
        if not hasattr(obj, "style_id") or obj.style_id is None:
            errors["style"] = "AI Style is required"
        if not hasattr(obj, "personality_id") or obj.personality_id is None:
            errors["personality"] = "AI Personality is required"

        if errors:
            raise FormValidationError(errors)

        contract_error = await validate_instance_contract(
            _request.state.session,
            style_id=getattr(obj, "style_id", None),
            personality_id=getattr(obj, "personality_id", None),
        )
        if contract_error is not None:
            raise FormValidationError({"personality": contract_error})

    fields_default_sort: ClassVar[list[tuple[str, bool]]] = [("created_at", True)]
    searchable_fields: ClassVar[list[str]] = ["qiao_id", "user_qiao_id"]
    sortable_fields: ClassVar[list[str]] = [
        "id",
        "user_id",
        "qiao_id",
        "status",
        "created_by",
        "created_at",
        "updated_at",
    ]

    fields: ClassVar[list[object]] = [
        StringField("id", label="ID", help_text="Internal instance ID"),
        _InstanceAvatarPreviewField(
            "avatar_preview",
            label="Avatar",
            help_text="Current avatar preview",
        ),
        HasOne(
            "user",
            identity="user",
            label="Owner User",
            help_text="User who owns this instance",
            required=True,
        ),
        StringField("user_qiao_id", label="User Qiao ID", help_text="Owning user qiao_id"),
        StringField(
            "qiao_id",
            label="Qiao ID",
            help_text="Optional external AI identifier; leave blank to auto-generate",
            required=False,
        ),
        HasOne(
            "persona",
            identity="ai_persona",
            label="Persona",
            help_text="Owning AI persona for source=persona; admin manual keeps this empty",
            required=False,
        ),
        HasOne(
            "template",
            identity="ai_template",
            label="Template",
            help_text="Selected template relation for source=persona",
            required=False,
        ),
        _TemplateDisplayNameField(),
        _ProfileRelatedStringField(
            "profile_nickname", profile_attr="nickname", label="Profile Nickname"
        ),
        _ProfileGenderField(),
        _ProfileOwnerTypeField(),
        HasOne(
            "style",
            identity="ai_style",
            label="AI Style",
            help_text="AI style for this instance",
            required=True,
        ),
        HasOne(
            "personality",
            identity="ai_personality",
            label="AI Personality",
            help_text="AI personality for this instance",
            required=True,
        ),
        StringField(
            "timezone",
            label="Timezone",
            help_text="IANA timezone for this instance (e.g., Asia/Shanghai)",
            required=True,
        ),
        IntegerField(
            "typing_speed_wpm",
            label="Typing Speed (WPM)",
            help_text="Words per minute used for typing simulation",
            required=True,
        ),
        _RelationshipDisplayNameField(),
        JSONField(
            "prompt_variables",
            label="Prompt Variables",
            help_text="Instance-specific prompt variable values",
        ),
        JSONField(
            "relationship_counts",
            label="Relationship Counts",
            help_text="Relationship type occurrence counts",
        ),
        HasOne(
            "llm_config",
            identity="llm_config",
            label="LLM Config",
            help_text=(
                "Preferred llm_configs.id for this instance (NULL falls back to system default)"
            ),
            required=False,
        ),
        JSONField(
            "request_params",
            label="Request Parameters",
            help_text="LLM request parameters (temperature, max_tokens, etc.)",
        ),
        JSONField(
            "creation_metadata",
            label="Creation Metadata",
            help_text="Snapshot of the payload recorded when this instance was created",
        ),
        IntegerEnumField(
            "created_by",
            enum=AIInstanceCreator,
            label="Created By",
            help_text="Who created this instance",
        ),
        IntegerEnumField(
            "status",
            enum=AIInstanceStatus,
            label="Status",
            help_text="Instance status: Active instances can be used (default: Active)",
            required=True,
        ),
        DateTimeField("created_at", label="Created At", help_text="Instance creation time"),
        DateTimeField("updated_at", label="Updated At", help_text="Last update time"),
    ]

    row_actions: ClassVar[list[str]] = ["view", "profile", "edit", "advanced_edit"]

    @link_row_action(
        name="advanced_edit",
        text="Advanced Edit",
        icon_class="fas fa-cogs",
    )
    def advanced_edit_row_action(self, _request: Request, pk: str) -> str:
        """Link to instance advanced edit."""
        return f"/qiao-dash/ai_instance/advanced-edit/{pk}"

    @link_row_action(
        name="profile",
        text="Profile",
        icon_class="fa fa-id-card",
    )
    def profile_detail_action(self, _request: Request, pk: int | str) -> str:
        """Open owner profile detail page."""
        return f"/admin-api/profile/owner-link/ai_instance/{pk}"


class AIInstanceDimensionView(ModelView):
    """AI Instance Dimension score view for per-dimension scoring management."""

    label = "Instance Dimensions"
    name = "Instance Dimensions"

    exclude_fields_from_create: ClassVar[list[str]] = [
        "id",
        "dimension_display_name",
        "created_at",
        "updated_at",
    ]
    exclude_fields_from_edit: ClassVar[list[str]] = [
        "id",
        "dimension_display_name",
        "instance_id",
        "dimension_id",
        "created_at",
        "updated_at",
    ]

    def can_delete(self, _request: Request) -> bool:
        """Disable delete action for relationship scores."""
        return False

    fields_default_sort: ClassVar[list[tuple[str, bool]]] = [("score", True)]
    searchable_fields: ClassVar[list[str]] = []
    sortable_fields: ClassVar[list[str]] = [
        "id",
        "instance_id",
        "dimension_id",
        "score",
        "position",
        "created_at",
        "updated_at",
    ]

    fields: ClassVar[list[object]] = [
        StringField("id", label="ID", help_text="Internal instance dimension ID"),
        HasOne(
            "instance",
            identity="ai_instance",
            label="AI Instance",
            help_text="AI instance",
            required=True,
        ),
        HasOne(
            "dimension",
            identity="ai_style_dimension",
            label="Style Dimension",
            help_text="Style dimension",
            required=True,
        ),
        _DimensionDisplayNameField(),
        IntegerField("score", label="Score", help_text="Current dimension score (0-1000)"),
        IntegerField("position", label="Position", help_text="Per mille position (0-1000)"),
        IntegerField(
            "position_mapping_algorithm",
            label="Position Mapping Algorithm",
            help_text="Position mapping algorithm: 1=direct, 2=V1",
        ),
        JSONField(
            "position_mapping_params",
            label="Position Mapping Parameters",
            help_text="Position mapping parameters (sensitivity and gain fields for V1)",
        ),
        DateTimeField("created_at", label="Created At", help_text="Score record creation time"),
        DateTimeField("updated_at", label="Updated At", help_text="Last update time"),
    ]

    async def validate(self, request: Request, data: FormData) -> None:
        """Custom validation for relationship scores."""
        errors = {}

        # Validate score range (if provided)
        if "score" in data and data["score"] is not None:
            score_obj = data["score"]
            if not isinstance(score_obj, int | float):
                errors["score"] = "Score must be a number"
            else:
                score_value = int(score_obj)
                if score_value < SCORE_MIN or score_value > SCORE_MAX:
                    errors["score"] = f"Score must be between {SCORE_MIN} and {SCORE_MAX}"

        # Validate position range (if provided)
        if "position" in data and data["position"] is not None:
            position_obj = data["position"]
            if not isinstance(position_obj, int | float):
                errors["position"] = "Position must be a number"
            else:
                position_value = int(position_obj)
                if position_value < POSITION_MIN or position_value > POSITION_MAX:
                    errors["position"] = (
                        f"Position must be between {POSITION_MIN} and {POSITION_MAX}"
                    )

        # If position is not provided, score must be provided to compute position
        if ("position" not in data or data["position"] is None) and not data.get("score"):
            errors["score"] = "Score is required when position is not provided"

        if errors:
            raise FormValidationError(errors)

        await super().validate(request, data)

    async def before_create(
        self, request: Request, data: FormData, obj: AIInstanceDimension
    ) -> None:
        """Auto-fill FKs, validate uniqueness, and compute default position if missing."""
        # Auto-fill foreign keys from submitted relation fields.
        obj.instance_id = _extract_relation_id(data.get("instance"))
        obj.dimension_id = _extract_relation_id(data.get("dimension"))

        # Validate required foreign keys
        errors = {}
        if not getattr(obj, "instance_id", None):
            errors["instance"] = "AI Instance is required"
        if not getattr(obj, "dimension_id", None):
            errors["dimension"] = "Relationship Dimension is required"

        session = request.state.session

        # Check uniqueness constraint: same instance + dimension
        if not errors:
            with session.no_autoflush:
                stmt = select(AIInstanceDimension).where(
                    AIInstanceDimension.instance_id == obj.instance_id,
                    AIInstanceDimension.dimension_id == obj.dimension_id,
                )
                result = await session.execute(stmt)
                existing_score = result.scalar_one_or_none()
                if existing_score:
                    errors["dimension"] = (
                        "Dimension score already exists for this instance and dimension "
                        f"(ID: {existing_score.id}). Each instance can only have one score "
                        "per dimension."
                    )

        if errors:
            raise FormValidationError(errors)

        # If position not provided, compute it from style's initial_position and score
        if getattr(obj, "position", None) is None:
            # Require score present to compute position
            if not getattr(obj, "score", None) and not data.get("score"):
                raise FormValidationError(
                    {"score": "Score is required when position is not provided"}
                )

            # Prevent premature autoflush while we read prerequisites and compute
            with session.no_autoflush:
                # Fetch instance style_id
                char_stmt = select(AIInstance.style_id).where(AIInstance.id == obj.instance_id)
                style_id = (await session.execute(char_stmt)).scalar_one_or_none()
                if style_id is None:
                    raise FormValidationError(
                        {"instance": "Selected instance has no style configured"}
                    )

                # Fetch initial_position for (style_id, dimension_id)
                init_stmt = select(AIStyleDimension.initial_position).where(
                    (AIStyleDimension.style_id == style_id)
                    & (AIStyleDimension.dimension_id == obj.dimension_id)
                )
                initial_position = (await session.execute(init_stmt)).scalar_one_or_none()
                if initial_position is None:
                    raise FormValidationError(
                        {
                            "dimension": (
                                "Initial position not configured for this style and dimension"
                            )
                        }
                    )

                # Determine algorithm and params with defaults
                algorithm_raw = (
                    getattr(obj, "position_mapping_algorithm", None)
                    or data.get("position_mapping_algorithm")
                    or 1
                )
                params_raw = (
                    getattr(obj, "position_mapping_params", None)
                    or data.get("position_mapping_params")
                    or {}
                )
                score_val = getattr(obj, "score", None) or data.get("score")
                if score_val is None:
                    raise FormValidationError({"score": "Score is required and cannot be None."})

                if not isinstance(score_val, int | float):
                    raise FormValidationError({"score": "Score must be numeric"})

                if not isinstance(params_raw, dict):
                    raise FormValidationError(
                        {"position_mapping_params": "Params must be a JSON object"}
                    )

                try:
                    score_float = float(score_val)
                    algorithm_int = int(cast(Any, algorithm_raw))
                    obj.position = int(
                        map_score_to_position(
                            algorithm=algorithm_int,
                            score=score_float,
                            initial_position=float(initial_position),
                            params=cast(dict[str, Any], params_raw) or {},
                        )
                    )
                except Exception as e:
                    raise FormValidationError(
                        {"position": f"Failed to calculate position: {e!s}"}
                    ) from e

    async def before_edit(
        self, _request: Request, _data: FormData, obj: AIInstanceDimension
    ) -> None:
        """Auto-fill foreign keys before editing score."""
        # Nothing to fill here beyond FKs


class AIInstanceMemoryView(ModelView):
    """Admin view for AI instance memories."""

    label = "Instance Memories"
    name = "Instance Memories"

    exclude_fields_from_create: ClassVar[list[str]] = [
        "id",
        "user_qiao_id",
        "instance_qiao_id",
        "created_at",
        "updated_at",
    ]
    exclude_fields_from_edit: ClassVar[list[str]] = [
        "id",
        "user_qiao_id",
        "instance_qiao_id",
        "created_at",
        "updated_at",
    ]

    fields_default_sort: ClassVar[list[tuple[str, bool]]] = [("created_at", True)]
    searchable_fields: ClassVar[list[str]] = [
        "content",
        "user_qiao_id",
        "instance_qiao_id",
    ]
    sortable_fields: ClassVar[list[str]] = [
        "instance_id",
        "user_id",
        "memory_type",
        "status",
        "importance",
        "created_at",
    ]

    fields: ClassVar[list[object]] = [
        StringField("id", label="ID"),
        HasOne(
            "instance",
            identity="ai_instance",
            label="AI Instance",
            help_text="Owning instance (auto-fills user信息)",
            required=True,
        ),
        StringField("instance_qiao_id", label="Instance Qiao ID"),
        StringField("user_qiao_id", label="User Qiao ID"),
        StringField(
            "memory_type",
            label="Memory Type",
            help_text="core 或 recent",
            required=True,
        ),
        IntegerField(
            "importance",
            label="Importance",
            help_text="1-10，控制寿命与排序",
            required=True,
        ),
        IntegerEnumField(
            "status",
            enum=AIInstanceMemoryStatus,
            label="Status",
            help_text="1=active, 2=archived",
            required=True,
        ),
        IntegerField(
            "source_message_id",
            label="Source Message ID",
            help_text="可选：来源会话条目",
            required=False,
        ),
        IntegerField(
            "source_strength",
            label="Source Strength",
            help_text="来源强度（1-5）",
            required=True,
        ),
        StringField(
            "fact_key",
            label="Fact Key",
            help_text="规则命中事实键",
            required=False,
        ),
        IntegerField(
            "reinforce_count",
            label="Reinforce Count",
            help_text="强化计数",
            required=True,
        ),
        DateTimeField("last_reinforced_at", label="Last Reinforced At"),
        IntegerField(
            "conflict_flag",
            label="Conflict Flag",
            help_text="冲突覆盖标记",
            required=False,
        ),
        TextAreaField(
            "content",
            label="Content",
            help_text="记忆内容",
            required=True,
        ),
        TextAreaField(
            "normalized_content",
            label="Normalized Content",
            help_text="标准化内容（去重键）",
            required=True,
        ),
        DateTimeField("refreshed_at", label="Refreshed At"),
        DateTimeField("expires_at", label="Expires At"),
        DateTimeField("created_at", label="Created At"),
        DateTimeField("updated_at", label="Updated At"),
    ]

    def can_create(self, _request: Request) -> bool:
        """Disable direct writes to enforce unified memory policy gateway."""
        return False

    def can_edit(self, _request: Request) -> bool:
        """Disable direct writes to enforce unified memory policy gateway."""
        return False

    def can_delete(self, _request: Request) -> bool:
        """Disable direct writes to enforce unified memory policy gateway."""
        return False

    async def before_create(
        self,
        _request: Request,
        _data: FormData,
        obj: AIInstanceMemory,
    ) -> None:
        """Ensure foreign keys/user metadata stay in sync."""
        errors = {}

        obj.instance_id = _extract_relation_id(_data.get("instance"))
        if not getattr(obj, "instance_id", None):
            errors["instance"] = "Instance is required"
        else:
            stmt = select(
                AIInstance.qiao_id,
                AIInstance.user_id,
                AIInstance.user_qiao_id,
            ).where(AIInstance.id == obj.instance_id)
            row = (await _request.state.session.execute(stmt)).first()
            if row is None:
                errors["instance"] = "Selected instance not found"
            else:
                instance_qiao_id, user_id, user_qiao_id = row
                obj.instance_qiao_id = instance_qiao_id
                obj.user_id = user_id
                obj.user_qiao_id = user_qiao_id

        if not getattr(obj, "user_id", None):
            errors["instance"] = "Owning user missing on selected instance"
        if not getattr(obj, "instance_qiao_id", None):
            errors["instance_qiao_id"] = "Instance qiao_id is required"
        if not getattr(obj, "user_qiao_id", None):
            errors["user_id"] = "User qiao_id is required"
        if errors:
            raise FormValidationError(errors)

    async def before_edit(
        self,
        _request: Request,
        _data: FormData,
        obj: AIInstanceMemory,
    ) -> None:
        """Disallow editing ownership; keep derived fields synced."""
        if "instance" in _data:
            obj.instance_id = _extract_relation_id(_data.get("instance"))

        if not getattr(obj, "instance_id", None):
            raise FormValidationError({"instance": "Instance is required"})

        stmt = select(
            AIInstance.qiao_id,
            AIInstance.user_id,
            AIInstance.user_qiao_id,
        ).where(AIInstance.id == obj.instance_id)
        row = (await _request.state.session.execute(stmt)).first()
        if row is None:
            raise FormValidationError({"instance": "Selected instance not found"})

        instance_qiao_id, user_id, user_qiao_id = row
        obj.instance_qiao_id = instance_qiao_id
        obj.user_id = user_id
        obj.user_qiao_id = user_qiao_id


# Create view instances
ai_instance_view = AIInstanceView(
    AIInstance,
    name="AI Instances",
    label="Instances",
    icon="fa fa-robot",
    identity="ai_instance",
)

ai_instance_dimension_view = AIInstanceDimensionView(
    AIInstanceDimension,
    name="Instance Dimensions",
    icon="fa fa-ruler",
    identity="ai_instance_dimension",
)

ai_instance_memory_view = AIInstanceMemoryView(
    AIInstanceMemory,
    name="Instance Memories",
    label="Instance Memories",
    icon="fa fa-book",
    identity="ai_instance_memory",
)

# Export instance views
AI_INSTANCE_VIEWS = [
    ai_instance_view,
    ai_instance_dimension_view,
    ai_instance_memory_view,
]
