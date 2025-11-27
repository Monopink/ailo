"""
AI Instance admin views.

This module contains Starlette-Admin views for AI instance system.
"""

from typing import Any, Dict

from admin.fields import LocalDateTimeField
from admin.views.base import IntegerEnumField
from enums import AIInstanceCreator, AIInstanceStatus, Gender, ProfileOwnerType
from models.ai import AIInstanceDimension
from models.ai.instance import AIInstance
from models.ai.style import AIStyleDimension
from models.base import generate_qiao_id
from models.profile import Profile
from models.user import User
from services.ai.utils.position_mapping import map_score_to_position
from sqlalchemy import select
from starlette.requests import Request
from starlette_admin import HasOne, IntegerField, JSONField, StringField, TextAreaField
from starlette_admin.actions import link_row_action
from starlette_admin.contrib.sqla import ModelView
from starlette_admin.exceptions import FormValidationError
from utils.snowflake import generate_snowflake_id


class _ProfileRelatedStringField(StringField):
    """Computed field showing Profile attribute for an AIInstance.

    It looks up profiles where owner_type=AI and owner_id=obj.id and returns
    the selected attribute as string.
    """

    def __init__(self, name: str, profile_attr: str, label: str):
        super().__init__(name=name, label=label)
        self._profile_attr = profile_attr
        self.read_only = True
        self.searchable = False
        self.orderable = False

    async def parse_obj(self, request, obj):  # type: ignore[override]
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
            profile_id, value = row
            if value is None:
                return None  # Framework will display as -null-
            if value == "":
                return "(Empty)"
            return str(value)
        except Exception:
            return "(Error)"


class _ProfileGenderField(StringField):
    """Computed field showing Profile.gender as enum name for an AIInstance."""

    def __init__(self, name: str = "profile_gender", label: str = "Profile Gender"):
        super().__init__(name=name, label=label)
        self.read_only = True
        self.searchable = False
        self.orderable = False

    async def parse_obj(self, request, obj):  # type: ignore[override]
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
            profile_id, value = row
            if value is None:
                return None  # Framework will display as -null-
            try:
                return Gender(int(value)).name
            except Exception:
                return str(value)
        except Exception:
            return "(Error)"


class _ProfileOwnerTypeField(StringField):
    """Computed field showing Profile.owner_type as enum name for an AIInstance."""

    def __init__(self, name: str = "profile_owner_type", label: str = "Profile Type"):
        super().__init__(name=name, label=label)
        self.read_only = True
        self.searchable = False
        self.orderable = False

    async def parse_obj(self, request, obj):  # type: ignore[override]
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
            profile_id, value = row
            if value is None:
                return None  # Framework will display as -null-
            try:
                return ProfileOwnerType(int(value)).name
            except Exception:
                return str(value)
        except Exception:
            return "(Error)"


class _RelationshipDisplayNameField(StringField):
    """Computed field to show relationship display_name for AIInstance."""

    def __init__(self, name: str = "relationship_display_name", label: str = "Relationship Name"):
        super().__init__(name=name, label=label)
        self.read_only = True
        self.searchable = False
        self.orderable = False

    async def parse_obj(self, request, obj):  # type: ignore[override]
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

    def __init__(self, name: str = "dimension_display_name", label: str = "Dimension Name"):
        super().__init__(name=name, label=label)
        self.read_only = True
        self.searchable = False
        self.orderable = False

    async def parse_obj(self, request, obj):  # type: ignore[override]
        try:
            if hasattr(obj, "dimension") and obj.dimension is not None:
                return str(getattr(obj.dimension, "display_name", "") or "")
            return ""
        except Exception:
            return ""


class AIInstanceView(ModelView):
    """Enhanced AI Instance view with proper field configuration and chat test functionality."""

    exclude_fields_from_create = [
        "id",
        "qiao_id",
        "user_id",
        "user_qiao_id",
        "created_by",
        "created_at",
        "updated_at",
        "profile_nickname",
        "profile_gender",
        "profile_owner_type",
        "relationship_display_name",
    ]
    exclude_fields_from_edit = [
        "id",
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
        "relationship_display_name",
    ]
    exclude_fields_from_list = [
        "creation_metadata",
    ]

    def is_active(self, request: Request) -> bool:
        """Check if current page is related to this model (including advanced-edit and chat-test)."""
        # Standard identity check for list/edit/detail pages
        if request.path_params.get("identity", None) == self.identity:
            return True

        # Check for advanced-edit or chat-test page with exact identity match
        path = request.scope["path"]
        return f"/{self.identity}/advanced-edit/" in path or f"/{self.identity}/chat-test/" in path

    def can_delete(self, request: Request) -> bool:
        return False

    async def create(self, request: Request, data: Dict[str, Any]) -> Any:
        """Override create to automatically set created_by field and generate IDs."""
        # Set created_by to 2 (Admin) for admin panel creations
        data["created_by"] = 2

        # Generate qiao_id if not provided
        if not data.get("qiao_id"):
            data["qiao_id"] = generate_qiao_id()

        # Generate id if not provided
        if not data.get("id"):
            data["id"] = generate_snowflake_id()

        return await super().create(request, data)

    async def edit(self, request: Request, pk: Any, data: Dict[str, Any]) -> Any:
        """Override edit to handle data processing."""
        return await super().edit(request, pk, data)

    async def before_create(self, request: Request, data: Dict[str, Any], obj: Any) -> None:
        """Auto-fill foreign keys and required fields before creating instance."""
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

        if hasattr(obj, "timezone") and (obj.timezone is None or obj.timezone == ""):
            obj.timezone = "Asia/Shanghai"

        if not hasattr(obj, "creation_metadata") or obj.creation_metadata is None:
            obj.creation_metadata = {}

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

    async def before_edit(self, request: Request, data: Dict[str, Any], obj: Any) -> None:
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

        if hasattr(obj, "timezone") and (obj.timezone is None or obj.timezone == ""):
            obj.timezone = "Asia/Shanghai"

        if not hasattr(obj, "creation_metadata") or obj.creation_metadata is None:
            obj.creation_metadata = {}

        # Validate required foreign keys
        errors = {}
        if not hasattr(obj, "style_id") or obj.style_id is None:
            errors["style"] = "AI Style is required"
        if not hasattr(obj, "personality_id") or obj.personality_id is None:
            errors["personality"] = "AI Personality is required"

        if errors:
            raise FormValidationError(errors)

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["qiao_id", "user_qiao_id"]
    sortable_fields = ["id", "user_id", "qiao_id", "status", "created_by", "created_at", "updated_at"]

    fields = [
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
        _ProfileRelatedStringField("profile_nickname", profile_attr="nickname", label="Profile Nickname"),
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
        _RelationshipDisplayNameField(),
        TextAreaField(
            "memory",
            label="Memory",
            help_text="Instance-specific memory and background information",
        ),
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
        JSONField(
            "request_params",
            label="Request Parameters",
            help_text="LLM request parameters (temperature, max_tokens, etc.)",
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
        LocalDateTimeField("created_at", label="Created At", help_text="Instance creation time"),
        LocalDateTimeField("updated_at", label="Updated At", help_text="Last update time"),
    ]

    row_actions = ["view", "edit", "advanced_edit", "chat_test"]

    @link_row_action(
        name="advanced_edit",
        text="Advanced Edit",
        icon_class="fas fa-cogs",
    )
    def advanced_edit_row_action(self, request: Request, pk: Any) -> str:
        """Link to instance advanced edit."""
        return f"/qiao-dash/ai_instance/advanced-edit/{pk}"

    @link_row_action(
        name="chat_test",
        text="Chat Test",
        icon_class="fas fa-flask",
    )
    def chat_test_row_action(self, request: Request, pk: Any) -> str:
        """Link to AI instance chat test page."""
        return f"/qiao-dash/ai_instance/chat-test/{pk}"


class AIInstanceDimensionView(ModelView):
    """AI Instance Dimension score view for per-dimension scoring management."""

    label = "Instance Dimensions"
    name = "Instance Dimensions"

    exclude_fields_from_create = ["id", "dimension_display_name", "created_at", "updated_at"]
    exclude_fields_from_edit = [
        "id",
        "dimension_display_name",
        "instance_id",
        "dimension_id",
        "created_at",
        "updated_at",
    ]

    def can_delete(self, request: Request) -> bool:
        """Disable delete action for relationship scores."""
        return False

    fields_default_sort = [("score", True)]
    searchable_fields = []
    sortable_fields = [
        "id",
        "instance_id",
        "dimension_id",
        "score",
        "position",
        "created_at",
        "updated_at",
    ]

    fields = [
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
        LocalDateTimeField("created_at", label="Created At", help_text="Score record creation time"),
        LocalDateTimeField("updated_at", label="Updated At", help_text="Last update time"),
    ]

    async def validate(self, request: Request, data: Dict[str, Any]) -> None:
        """Custom validation for relationship scores."""
        errors = {}

        # Validate score range (if provided)
        if "score" in data and data["score"] is not None:
            score = data["score"]
            if score < 0 or score > 1000:
                errors["score"] = "Score must be between 0 and 1000"

        # Validate position range (if provided)
        if "position" in data and data["position"] is not None:
            position = data["position"]
            if position < 0 or position > 1000:
                errors["position"] = "Position must be between 0 and 1000"

        # If position is not provided, score must be provided to compute position
        if ("position" not in data or data["position"] is None) and not data.get("score"):
            errors["score"] = "Score is required when position is not provided"

        if errors:
            raise FormValidationError(errors)

        return await super().validate(request, data)

    async def before_create(self, request: Request, data: Dict[str, Any], obj: Any) -> None:
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
                        f"Dimension score already exists for this instance and dimension "
                        f"(ID: {existing_score.id}). Each instance can only have one score per dimension."
                    )

        if errors:
            raise FormValidationError(errors)

        # If position not provided, compute it from style's initial_position and score
        if getattr(obj, "position", None) is None:
            # Require score present to compute position
            if not getattr(obj, "score", None) and not data.get("score"):
                raise FormValidationError({"score": "Score is required when position is not provided"})

            # Prevent premature autoflush while we read prerequisites and compute
            with session.no_autoflush:
                # Fetch instance style_id
                char_stmt = select(AIInstance.style_id).where(AIInstance.id == obj.instance_id)
                style_id = (await session.execute(char_stmt)).scalar_one_or_none()
                if style_id is None:
                    raise FormValidationError({"instance": "Selected instance has no style configured"})

                # Fetch initial_position for (style_id, dimension_id)
                init_stmt = select(AIStyleDimension.initial_position).where(
                    (AIStyleDimension.style_id == style_id)
                    & (AIStyleDimension.dimension_id == obj.dimension_id)
                )
                initial_position = (await session.execute(init_stmt)).scalar_one_or_none()
                if initial_position is None:
                    raise FormValidationError(
                        {"dimension": "Initial position not configured for this style and dimension"}
                    )

                # Determine algorithm and params with defaults
                algorithm = (
                    getattr(obj, "position_mapping_algorithm", None)
                    or data.get("position_mapping_algorithm")
                    or 1
                )
                params = (
                    getattr(obj, "position_mapping_params", None)
                    or data.get("position_mapping_params")
                    or {}
                )
                score_val = getattr(obj, "score", None) or data.get("score")
                if score_val is None:
                    raise FormValidationError({"score": "Score is required and cannot be None."})

                try:
                    score_float = float(score_val)
                    obj.position = int(
                        map_score_to_position(
                            algorithm=int(algorithm),
                            score=score_float,
                            initial_position=float(initial_position),
                            params=params or {},
                        )
                    )
                except Exception as e:
                    raise FormValidationError({"position": f"Failed to calculate position: {str(e)}"})

    async def before_edit(self, request: Request, data: Dict[str, Any], obj: Any) -> None:
        """Auto-fill foreign keys before editing score."""
        # Nothing to fill here beyond FKs


# Create view instances
ai_instance_view = AIInstanceView(
    AIInstance, name="AI Instances", label="Instances", icon="fa fa-robot", identity="ai_instance"
)

ai_instance_dimension_view = AIInstanceDimensionView(
    AIInstanceDimension, name="Instance Dimensions", icon="fa fa-ruler", identity="ai_instance_dimension"
)

# Export instance views
AI_INSTANCE_VIEWS = [
    ai_instance_view,
    ai_instance_dimension_view,
]
