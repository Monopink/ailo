"""AI Instance admin views.

This module contains Starlette-Admin views for AI instance system.
"""

from collections.abc import MutableMapping
from enum import IntEnum
from typing import Any, ClassVar, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from starlette_admin import (
    DateTimeField,
    HasOne,
    IntegerField,
    JSONField,
    StringField,
    TextAreaField,
)
from starlette_admin.actions import link_row_action
from starlette_admin.contrib.sqla import ModelView
from starlette_admin.exceptions import FormValidationError

from app.admin.views.base import IntegerEnumField
from app.crud.ai import ai_instance as ai_instance_crud
from app.enums import AIInstanceCreator, AIInstanceStatus, Gender, ProfileOwnerType
from app.models.ai import AIInstanceDimension
from app.models.ai.instance import AIInstance
from app.models.ai.memory import AIInstanceMemory
from app.models.ai.personality import AIPersonality
from app.models.ai.style import AIDimension, AIStyleDimension
from app.models.base import generate_qiao_id
from app.models.profile import Profile
from app.models.user import User
from app.services.ai.profile_integrity import ensure_instance_profile
from app.services.ai.relationship_scoring import initialize_instance_relationship
from app.services.ai.response_schema import validate_style_personality_contract
from app.services.ai.utils.position_mapping import map_score_to_position
from app.utils.logging import get_logger
from app.utils.snowflake import generate_snowflake_id

FormData = MutableMapping[str, object]
logger = get_logger(__name__)

POSITION_MIN = 0
POSITION_MAX = 1000
SCORE_MIN = 0
SCORE_MAX = 1000


class MemoryStatus(IntEnum):
    """Enum for AI instance memory status field."""

    ACTIVE = 1
    ARCHIVED = 2


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

    async def parse_obj(self, _request: Request, obj: AIInstance) -> str | None:
        try:
            # Check if relationship exists
            if not hasattr(obj, "relationship"):
                return "(No Relationship Attr)"

            # Relationship is None (not assigned)
            if obj.relationship is None:
                return None  # Framework will display as -null-

            # Relationship exists, get display_name
            display_name = getattr(obj.relationship, "display_name", None)
            if display_name is None:
                return None  # Framework will display as -null-
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

    async def parse_obj(self, _request: Request, obj: AIInstanceDimension) -> str:
        try:
            if hasattr(obj, "dimension") and obj.dimension is not None:
                return str(getattr(obj.dimension, "display_name", "") or "")
        except Exception:
            return ""
        return ""


class AIInstanceView(ModelView):
    """Enhanced AI Instance view with proper field configuration."""

    exclude_fields_from_create: ClassVar[list[str]] = [
        "id",
        "qiao_id",
        "user_id",
        "user_qiao_id",
        "username",
        "created_by",
        "created_at",
        "updated_at",
        "profile_nickname",
        "profile_gender",
        "profile_owner_type",
        "relationship_display_name",
    ]
    exclude_fields_from_edit: ClassVar[list[str]] = [
        "id",
        "qiao_id",
        "user",
        "user_id",
        "user_qiao_id",
        "username",
        "created_by",
        "created_at",
        "updated_at",
        "profile_nickname",
        "profile_gender",
        "profile_owner_type",
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

    async def create(self, request: Request, data: FormData) -> AIInstance:
        """Override create to automatically set created_by field and generate IDs."""
        # Set created_by to 2 (Admin) for admin panel creations
        data["created_by"] = 2

        # Generate qiao_id if not provided
        if not data.get("qiao_id"):
            data["qiao_id"] = generate_qiao_id()

        # Generate id if not provided
        if not data.get("id"):
            data["id"] = generate_snowflake_id()

        created_instance = await super().create(request, data)

        session = request.state.session
        try:
            await initialize_instance_relationship(session, instance_id=int(created_instance.id))
            await session.commit()
        except Exception as exc:
            await session.rollback()
            logger.error(
                "admin_instance_relationship_initialization_failed",
                instance_id=getattr(created_instance, "id", None),
                error=str(exc),
                exc_info=True,
            )
            try:
                await ai_instance_crud.remove(session, record_id=int(created_instance.id))
            except Exception as cleanup_exc:
                logger.error(
                    "admin_instance_cleanup_failed_after_relationship_init_error",
                    instance_id=getattr(created_instance, "id", None),
                    error=str(cleanup_exc),
                    exc_info=True,
                )
            raise FormValidationError(
                {"relationship": "Failed to initialize relationship for new instance"}
            ) from exc

        return created_instance

    async def edit(self, request: Request, pk: str, data: FormData) -> AIInstance:
        """Override edit to handle data processing."""
        return await super().edit(request, pk, data)

    async def before_create(self, request: Request, data: FormData, obj: AIInstance) -> None:
        """Auto-fill foreign keys and required fields before creating instance."""
        if not getattr(obj, "id", None):
            obj.id = generate_snowflake_id()
        if not getattr(obj, "qiao_id", None):
            obj.qiao_id = generate_qiao_id()

        # Set created_by to 2 (Admin) for admin panel creations
        obj.created_by = 2

        # Auto-fill user_id and user_qiao_id from selected user
        user = data.get("user")
        if user and isinstance(user, User):
            obj.user_id = user.id
            obj.user_qiao_id = user.qiao_id

        # Auto-fill foreign keys from HasOne relationships
        if hasattr(obj, "style") and obj.style is not None:
            obj.style_id = obj.style.id
        if hasattr(obj, "personality") and obj.personality is not None:
            obj.personality_id = obj.personality.id
        if hasattr(obj, "relationship") and obj.relationship is not None:
            obj.relationship_id = obj.relationship.id
        else:
            obj.relationship_id = None
        if hasattr(obj, "llm_config") and obj.llm_config is not None:
            obj.llm_config_id = obj.llm_config.id
        else:
            obj.llm_config_id = None

        if hasattr(obj, "timezone") and (obj.timezone is None or obj.timezone == ""):
            obj.timezone = "Asia/Shanghai"

        if not hasattr(obj, "creation_metadata") or obj.creation_metadata is None:
            obj.creation_metadata = {}
        metadata = obj.creation_metadata if isinstance(obj.creation_metadata, dict) else {}
        metadata["source"] = "admin_manual"
        obj.creation_metadata = metadata
        obj.username = None

        # Validate required foreign keys
        errors = {}
        if not hasattr(obj, "user_id") or obj.user_id is None:
            errors["user"] = "Owner User is required"
        if not hasattr(obj, "style_id") or obj.style_id is None:
            errors["style"] = "AI Style is required"
        if not hasattr(obj, "personality_id") or obj.personality_id is None:
            errors["personality"] = "AI Personality is required"

        if errors:
            raise FormValidationError(errors)

        contract_error = await self._validate_instance_contract(
            request.state.session,
            style_id=getattr(obj, "style_id", None),
            personality_id=getattr(obj, "personality_id", None),
        )
        if contract_error is not None:
            raise FormValidationError({"personality": contract_error})

        try:
            await ensure_instance_profile(
                request.state.session,
                instance=obj,
                source="admin.ai_instance.before_create",
            )
        except (TypeError, ValueError) as exc:
            logger.error(
                "admin_instance_profile_validation_failed",
                error=str(exc),
                instance_id=getattr(obj, "id", None),
                instance_qiao_id=getattr(obj, "qiao_id", None),
            )
            raise FormValidationError({"qiao_id": str(exc)}) from exc

    async def before_edit(self, _request: Request, _data: FormData, obj: AIInstance) -> None:
        """Auto-fill foreign keys before editing instance."""
        # Auto-fill foreign keys from HasOne relationships
        if hasattr(obj, "style") and obj.style is not None:
            obj.style_id = obj.style.id
        if hasattr(obj, "personality") and obj.personality is not None:
            obj.personality_id = obj.personality.id
        if hasattr(obj, "relationship") and obj.relationship is not None:
            obj.relationship_id = obj.relationship.id
        else:
            obj.relationship_id = None
        if hasattr(obj, "llm_config") and obj.llm_config is not None:
            obj.llm_config_id = obj.llm_config.id
        else:
            obj.llm_config_id = None

        if hasattr(obj, "timezone") and (obj.timezone is None or obj.timezone == ""):
            obj.timezone = "Asia/Shanghai"

        if not hasattr(obj, "creation_metadata") or obj.creation_metadata is None:
            obj.creation_metadata = {}
        if isinstance(obj.creation_metadata, dict):
            source = obj.creation_metadata.get("source")
            if source == "admin_manual":
                obj.username = None

        # Validate required foreign keys
        errors = {}
        if not hasattr(obj, "style_id") or obj.style_id is None:
            errors["style"] = "AI Style is required"
        if not hasattr(obj, "personality_id") or obj.personality_id is None:
            errors["personality"] = "AI Personality is required"

        if errors:
            raise FormValidationError(errors)

        contract_error = await self._validate_instance_contract(
            _request.state.session,
            style_id=getattr(obj, "style_id", None),
            personality_id=getattr(obj, "personality_id", None),
        )
        if contract_error is not None:
            raise FormValidationError({"personality": contract_error})

    @staticmethod
    async def _validate_instance_contract(
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
    searchable_fields: ClassVar[list[str]] = ["qiao_id", "username", "user_qiao_id"]
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
        HasOne(
            "user",
            identity="user",
            label="Owner User",
            help_text="User who owns this instance",
            required=True,
        ),
        StringField("user_qiao_id", label="User Qiao ID", help_text="Owning user qiao_id"),
        StringField("qiao_id", label="Qiao ID", help_text="External AI identifier"),
        StringField(
            "username",
            label="Username",
            help_text="Runtime username snapshot; admin manual creation keeps this empty",
            required=False,
        ),
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
        HasOne(
            "relationship",
            identity="ai_relationship",
            label="Current Relationship",
            help_text="Current relationship type",
            required=False,
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

    row_actions: ClassVar[list[str]] = ["view", "edit", "advanced_edit"]

    @link_row_action(
        name="advanced_edit",
        text="Advanced Edit",
        icon_class="fas fa-cogs",
    )
    def advanced_edit_row_action(self, _request: Request, pk: str) -> str:
        """Link to instance advanced edit."""
        return f"/qiao-dash/ai_instance/advanced-edit/{pk}"


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
        # Auto-fill foreign keys from HasOne relationships
        if hasattr(obj, "instance") and obj.instance is not None:
            obj.instance_id = obj.instance.id
        if hasattr(obj, "dimension") and obj.dimension is not None:
            obj.dimension_id = obj.dimension.id

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
            enum=MemoryStatus,
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
        TextAreaField(
            "content",
            label="Content",
            help_text="记忆内容",
            required=True,
        ),
        DateTimeField("refreshed_at", label="Refreshed At"),
        DateTimeField("expires_at", label="Expires At"),
        DateTimeField("created_at", label="Created At"),
        DateTimeField("updated_at", label="Updated At"),
    ]

    async def before_create(
        self,
        _request: Request,
        _data: FormData,
        obj: AIInstanceMemory,
    ) -> None:
        """Ensure foreign keys/user metadata stay in sync."""
        errors = {}
        if hasattr(obj, "instance") and obj.instance is not None:
            obj.instance_id = obj.instance.id
            obj.instance_qiao_id = getattr(obj.instance, "qiao_id", obj.instance_qiao_id)
            obj.user_id = obj.instance.user_id
            obj.user_qiao_id = obj.instance.user_qiao_id
        if not getattr(obj, "instance_id", None):
            errors["instance"] = "Instance is required"
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
        if hasattr(obj, "instance") and obj.instance is not None:
            obj.instance_id = obj.instance.id
            obj.instance_qiao_id = getattr(obj.instance, "qiao_id", obj.instance_qiao_id)
            obj.user_id = obj.instance.user_id
            obj.user_qiao_id = obj.instance.user_qiao_id


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
