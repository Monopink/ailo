"""
AI Character admin views.

This module contains Starlette-Admin views for AI character system.
"""

from typing import Any, Dict
from starlette.requests import Request
from starlette_admin.contrib.sqla import ModelView
from starlette_admin import IntegerField, StringField, TextAreaField, HasOne, JSONField
from starlette_admin.actions import link_row_action
from starlette_admin.exceptions import FormValidationError

from models.ai.character import AICharacter
from models.ai import AICharacterDimension
from admin.views.base import IntegerEnumField
from admin.fields import LocalDateTimeField
from enums import (
    AICharacterCreator,
    AICharacterStatus,
    Gender,
    ProfileOwnerType,
)


class _ProfileRelatedStringField(StringField):
    """Computed field showing Profile attribute for an AICharacter.

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
            from sqlalchemy import select
            from models.profile import Profile

            session = request.state.session
            stmt = select(getattr(Profile, self._profile_attr)).where(
                Profile.owner_id == obj.id, Profile.owner_type == ProfileOwnerType.AI
            )
            result = await session.execute(stmt)
            value = result.scalar_one_or_none()
            return "" if value is None else str(value)
        except Exception:
            return ""


class _ProfileGenderField(StringField):
    """Computed field showing Profile.gender as enum name for an AICharacter."""

    def __init__(self, name: str = "profile_gender", label: str = "Profile Gender"):
        super().__init__(name=name, label=label)
        self.read_only = True
        self.searchable = False
        self.orderable = False

    async def parse_obj(self, request, obj):  # type: ignore[override]
        try:
            from sqlalchemy import select
            from models.profile import Profile

            session = request.state.session
            stmt = select(Profile.gender).where(
                Profile.owner_id == obj.id, Profile.owner_type == ProfileOwnerType.AI
            )
            result = await session.execute(stmt)
            value = result.scalar_one_or_none()
            if value is None:
                return ""
            try:
                return Gender(int(value)).name
            except Exception:
                return str(value)
        except Exception:
            return ""


class _RelationshipDisplayNameField(StringField):
    """Computed field to show relationship display_name for AICharacter."""

    def __init__(self, name: str = "relationship_display_name", label: str = "Current Relationship"):
        super().__init__(name=name, label=label)
        self.read_only = True
        self.searchable = False
        self.orderable = False

    async def parse_obj(self, request, obj):  # type: ignore[override]
        try:
            if hasattr(obj, "relationship") and obj.relationship is not None:
                return str(obj.relationship.display_name)
            return ""
        except Exception:
            return ""


class _DimensionDisplayNameField(StringField):
    """Computed field to show dimension display_name for AICharacterDimension."""

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


class AICharacterView(ModelView):
    """Enhanced AI Character view with proper field configuration and chat test functionality."""

    exclude_fields_from_create = [
        "id",
        "qiao_id",
        "created_by",
        "created_at",
        "updated_at",
        "profile_nickname",
        "profile_gender",
        "relationship_display_name",
    ]
    exclude_fields_from_edit = [
        "id",
        "qiao_id",
        "created_by",
        "created_at",
        "updated_at",
        "profile_nickname",
        "profile_gender",
        "relationship_display_name",
    ]
    exclude_fields_from_list = []

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
            from models.base import generate_qiao_id

            data["qiao_id"] = generate_qiao_id()

        # Generate id if not provided
        if not data.get("id"):
            from utils.snowflake import generate_snowflake_id

            data["id"] = generate_snowflake_id()

        return await super().create(request, data)

    async def edit(self, request: Request, pk: Any, data: Dict[str, Any]) -> Any:
        """Override edit to handle data processing."""
        # Convert empty string to None for category
        if "category" in data and data["category"] == "":
            data["category"] = None
        return await super().edit(request, pk, data)

    async def before_create(self, request: Request, data: Dict[str, Any], obj: Any) -> None:
        """Auto-fill foreign keys and required fields before creating character."""
        # Set created_by to 2 (Admin) for admin panel creations
        obj.created_by = 2

        # Convert empty string to None for category
        if hasattr(obj, "category") and obj.category == "":
            obj.category = None

        if hasattr(obj, "timezone") and (obj.timezone is None or obj.timezone == ""):
            obj.timezone = "Asia/Shanghai"

        # Auto-fill foreign keys from HasOne relationships
        # starlette-admin's HasOne sets the relationship object but not the FK field
        if hasattr(obj, "style") and obj.style is not None:
            obj.style_id = obj.style.id
        if hasattr(obj, "personality") and obj.personality is not None:
            obj.personality_id = obj.personality.id

        # Validate required foreign keys
        errors = {}
        if not hasattr(obj, "style_id") or obj.style_id is None:
            errors["style"] = "AI Style is required"
        if not hasattr(obj, "personality_id") or obj.personality_id is None:
            errors["personality"] = "AI Personality is required"

        if errors:
            raise FormValidationError(errors)

    async def before_edit(self, request: Request, data: Dict[str, Any], obj: Any) -> None:
        """Auto-fill foreign keys before editing character."""
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

        # Validate required foreign keys
        errors = {}
        if not hasattr(obj, "style_id") or obj.style_id is None:
            errors["style"] = "AI Style is required"
        if not hasattr(obj, "personality_id") or obj.personality_id is None:
            errors["personality"] = "AI Personality is required"

        if errors:
            raise FormValidationError(errors)

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["qiao_id", "category"]
    sortable_fields = ["id", "qiao_id", "category", "status", "created_by", "created_at", "updated_at"]

    fields = [
        StringField("id", label="ID", help_text="Internal character ID"),
        StringField("qiao_id", label="Character ID", help_text="Unique character identifier"),
        StringField("category", label="Category", help_text="Character category classification"),
        _ProfileRelatedStringField("profile_nickname", profile_attr="nickname", label="Profile Nickname"),
        _ProfileGenderField(),
        HasOne(
            "style",
            identity="ai_style",
            label="AI Style",
            help_text="AI style for this character",
            required=True,
        ),
        HasOne(
            "personality",
            identity="ai_personality",
            label="AI Personality",
            help_text="AI personality for this character",
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
            help_text="Character-specific memory and background information",
        ),
        JSONField(
            "prompt_variables",
            label="Prompt Variables",
            help_text="Character-specific prompt variable values",
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
            help_text="IANA timezone for this character (e.g., Asia/Shanghai)",
            required=True,
        ),
        IntegerField(
            "typing_speed_wpm",
            label="Typing Speed (WPM)",
            help_text="Words per minute used for typing simulation",
            required=True,
        ),
        IntegerEnumField(
            "created_by",
            enum=AICharacterCreator,
            label="Created By",
            help_text="Who created this character",
        ),
        IntegerEnumField(
            "status",
            enum=AICharacterStatus,
            label="Status",
            help_text="Character status: Active characters can be used (default: Active)",
            required=True,
        ),
        LocalDateTimeField("created_at", label="Created At", help_text="Character creation time"),
        LocalDateTimeField("updated_at", label="Updated At", help_text="Last update time"),
    ]

    row_actions = ["view", "edit", "advanced_edit", "chat_test"]

    @link_row_action(
        name="advanced_edit",
        text="Advanced Edit",
        icon_class="fas fa-cogs",
    )
    def advanced_edit_row_action(self, request: Request, pk: Any) -> str:
        """Link to edit character JSON fields."""
        return f"/qiao-dash/ai_character/advanced-edit/{pk}"

    @link_row_action(
        name="chat_test",
        text="Chat Test",
        icon_class="fas fa-flask",
    )
    def chat_test_row_action(self, request: Request, pk: Any) -> str:
        """Link to AI character chat test page."""
        return f"/qiao-dash/ai_character/chat-test/{pk}"


class AICharacterDimensionView(ModelView):
    """AI Character Dimension score view for per-dimension scoring management."""

    label = "Character Dimensions"
    name = "Character Dimensions"

    exclude_fields_from_create = ["id", "dimension_display_name", "created_at", "updated_at"]
    exclude_fields_from_edit = [
        "id",
        "dimension_display_name",
        "character_id",
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
        "character_id",
        "dimension_id",
        "score",
        "position",
        "created_at",
        "updated_at",
    ]

    fields = [
        StringField("id", label="ID", help_text="Internal character dimension ID"),
        HasOne(
            "character",
            identity="ai_character",
            label="AI Character",
            help_text="AI character",
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
        from sqlalchemy import select
        from models.ai.style import AIStyleDimension
        from services.ai.utils.position_mapping import map_score_to_position

        # Auto-fill foreign keys from HasOne relationships
        if hasattr(obj, "character") and obj.character is not None:
            obj.character_id = obj.character.id
        if hasattr(obj, "dimension") and obj.dimension is not None:
            obj.dimension_id = obj.dimension.id

        # Validate required foreign keys
        errors = {}
        if not getattr(obj, "character_id", None):
            errors["character"] = "AI Character is required"
        if not getattr(obj, "dimension_id", None):
            errors["dimension"] = "Relationship Dimension is required"

        session = request.state.session

        # Check uniqueness constraint: same character + dimension
        if not errors:
            with session.no_autoflush:
                stmt = select(AICharacterDimension).where(
                    AICharacterDimension.character_id == obj.character_id,
                    AICharacterDimension.dimension_id == obj.dimension_id,
                )
                result = await session.execute(stmt)
                existing_score = result.scalar_one_or_none()
                if existing_score:
                    errors["dimension"] = (
                        f"Dimension score already exists for this character and dimension "
                        f"(ID: {existing_score.id}). Each character can only have one score per dimension."
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
                # Fetch character style_id
                char_stmt = select(AICharacter.style_id).where(AICharacter.id == obj.character_id)
                style_id = (await session.execute(char_stmt)).scalar_one_or_none()
                if style_id is None:
                    raise FormValidationError({"character": "Selected character has no style configured"})

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
ai_character_view = AICharacterView(
    AICharacter, name="AI Characters", label="Characters", icon="fa fa-robot", identity="ai_character"
)

ai_character_dimension_view = AICharacterDimensionView(
    AICharacterDimension, name="Character Dimensions", icon="fa fa-ruler", identity="ai_character_dimension"
)

# Export character views
AI_CHARACTER_VIEWS = [
    ai_character_view,
    ai_character_dimension_view,
]
