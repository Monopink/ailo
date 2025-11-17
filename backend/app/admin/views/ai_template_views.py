"""
AI Template admin views.

This module contains Starlette-Admin views for AI character and profile templates.
"""

from typing import Any, Dict
from starlette.requests import Request
from starlette_admin.contrib.sqla import ModelView
from starlette_admin import StringField, TextAreaField, HasOne, IntegerField, JSONField
from admin.fields import LocalDateTimeField
from starlette_admin.actions import link_row_action
from starlette_admin.exceptions import FormValidationError

from models.ai.template import AICharacterTemplate, AIProfileTemplate
from admin.views.base import IntegerEnumField, CategoryEnumField
from enums import (
    AIProfileCategory,
    AIStyleStatus,
    Gender,
    ReusableStatus,
    PROFILE_CATEGORY_API_TO_DB,
    PROFILE_CATEGORY_DB_TO_API,
)


class _CharacterTemplateDisplayNameField(StringField):
    """Computed field to show associated Character Template display_name for AIProfileTemplate list."""

    def __init__(
        self, name: str = "character_template_display_name", label: str = "Character Template Name"
    ):
        super().__init__(name=name, label=label)
        self.read_only = True
        self.searchable = False
        self.orderable = False

    async def parse_obj(self, request, obj):  # type: ignore[override]
        try:
            # Prefer already-loaded relation
            if hasattr(obj, "character_template") and obj.character_template is not None:
                value = getattr(obj.character_template, "display_name", None)
                if value:
                    return str(value)

            # Fallback: query by character_template_id
            from sqlalchemy import select
            from models.ai.template import AICharacterTemplate

            character_template_id = getattr(obj, "character_template_id", None)
            if not character_template_id:
                return ""

            session = request.state.session
            result = await session.execute(
                select(AICharacterTemplate.display_name).where(
                    AICharacterTemplate.id == character_template_id
                )
            )
            value = result.scalar_one_or_none()
            return "" if value is None else str(value)
        except Exception:
            return ""



class AICharacterTemplateView(ModelView):
    """Enhanced AI Character Template view with proper field configuration."""

    exclude_fields_from_create = ["id", "profile_count", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "profile_count", "created_at", "updated_at"]
    exclude_fields_from_list = []

    def is_active(self, request: Request) -> bool:
        """Check if current page is related to this model (including advanced-edit)."""
        # Standard identity check for list/edit/detail pages
        if request.path_params.get("identity", None) == self.identity:
            return True

        # Check for advanced-edit page with exact identity match
        path = request.scope["path"]
        return f"/{self.identity}/advanced-edit/" in path

    def can_delete(self, request):
        return False

    async def before_create(self, request: Request, data: Dict[str, Any], obj: Any) -> None:
        """Auto-fill foreign keys before creating character template."""
        # Auto-fill foreign keys from HasOne relationships
        if hasattr(obj, "style") and obj.style is not None:
            obj.style_id = obj.style.id
        if hasattr(obj, "personality") and obj.personality is not None:
            obj.personality_id = obj.personality.id
        if hasattr(obj, "profile") and obj.profile is not None:
            obj.profile_id = obj.profile.id

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
    searchable_fields = []
    sortable_fields = [
        "id",
        "style_id",
        "personality_id",
        "status",
        "is_reusable",
        "profile_count",
        "created_at",
        "updated_at",
    ]

    fields = [
        StringField("id", label="ID", help_text="Internal character template ID"),
        StringField(
            "display_name",
            label="Display Name",
            help_text="Human-readable name for this character template",
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
        TextAreaField(
            "memory",
            label="Memory Settings",
            help_text="Default memory settings for characters using this template",
        ),
        "prompt_variables",
        JSONField(
            "request_params",
            label="Request Parameters",
            help_text="LLM request parameters (temperature, max_tokens, etc.) - inherited by character instances",
        ),
        StringField(
            "timezone",
            label="Timezone",
            help_text="IANA timezone for instantiated characters (e.g., Asia/Shanghai)",
            required=True,
        ),
        IntegerField(
            "typing_speed_wpm",
            label="Typing Speed (WPM)",
            help_text="Default typing speed that downstream characters inherit (words per minute)",
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
        HasOne(
            "profile",
            identity="ai_profile_template",
            label="Profile Template",
            help_text="Associated profile template (for single-use templates)",
            required=False,
        ),
        IntegerEnumField(
            "status",
            enum=AIStyleStatus,
            label="Status",
            help_text="Active templates can be used",
            required=True,
        ),
        IntegerField("profile_count", label="Profile Count", help_text="Associated profile count"),
        LocalDateTimeField("created_at", label="Created At", help_text="Creation time"),
        LocalDateTimeField("updated_at", label="Updated At", help_text="Last update time"),
    ]

    row_actions = ["view", "edit", "advanced_edit"]

    @link_row_action(
        name="advanced_edit",
        text="Advanced Edit",
        icon_class="fas fa-cogs",
    )
    def advanced_edit_row_action(self, request: Request, pk: Any) -> str:
        """Link to edit character template JSON fields."""
        return f"/qiao-dash/ai_character_template/advanced-edit/{pk}"


class AIProfileTemplateView(ModelView):
    """Enhanced AI Profile Template view with proper field configuration."""

    exclude_fields_from_create = [
        "id",
        "character_template_display_name",
        "qiao_id",
        "created_at",
        "updated_at",
    ]
    exclude_fields_from_edit = [
        "id",
        "character_template_display_name",
        "qiao_id",
        "created_at",
        "updated_at",
    ]

    def can_delete(self, request):
        return False

    async def before_create(self, request: Request, data: Dict[str, Any], obj: Any) -> None:
        """Auto-fill foreign keys and generate IDs before creating profile template."""
        # Auto-fill character_template_id from HasOne relationship
        if hasattr(obj, "character_template") and obj.character_template is not None:
            obj.character_template_id = obj.character_template.id

        # Validate required foreign key
        if not hasattr(obj, "character_template_id") or obj.character_template_id is None:
            raise FormValidationError({"character_template": "Character Template is required"})

        # Generate qiao_id if not provided
        if not hasattr(obj, "qiao_id") or not obj.qiao_id:
            from models.base import generate_qiao_id

            obj.qiao_id = generate_qiao_id()

        # Generate id if not provided (Snowflake ID)
        if not hasattr(obj, "id") or not obj.id:
            from utils.snowflake import generate_snowflake_id

            obj.id = generate_snowflake_id()

        # Convert category from form (int) or from obj to DB string value
        # Ensures DB receives canonical strings even if the UI didn't touch category
        raw = data.get("category", getattr(obj, "category", None))
        if raw is None or raw == "":
            data["category"] = None
            obj.category = None
        else:
            mapped = None
            try:
                num = int(raw)
                enum_val = AIProfileCategory(num)
                mapped = PROFILE_CATEGORY_API_TO_DB.get(enum_val)
            except Exception:
                raw_str = str(raw)
                if raw_str in PROFILE_CATEGORY_DB_TO_API:
                    mapped = raw_str
            data["category"] = mapped
            obj.category = mapped

    async def before_edit(self, request: Request, data: Dict[str, Any], obj: Any) -> None:
        """Convert category from int to string before editing."""
        import logging

        logger = logging.getLogger(__name__)

        # Convert category from int (API enum) or pass-through canonical string
        # Also handles when UI didn't submit category but after_find converted obj.category to int
        raw = data.get("category", getattr(obj, "category", None))
        logger.info(
            f"[AIProfileTemplate before_edit] raw category from data: {data.get('category')}, from obj: {getattr(obj, 'category', None)}, final raw: {raw}"
        )
        if raw is None or raw == "":
            data["category"] = None
            obj.category = None
        else:
            mapped = None
            try:
                num = int(raw)
                enum_val = AIProfileCategory(num)
                mapped = PROFILE_CATEGORY_API_TO_DB.get(enum_val)
            except Exception:
                raw_str = str(raw)
                if raw_str in PROFILE_CATEGORY_DB_TO_API:
                    mapped = raw_str
            data["category"] = mapped
            obj.category = mapped

        logger.info(
            f"[AIProfileTemplate before_edit] final mapped category: {mapped}, data['category']: {data.get('category')}, obj.category: {obj.category}"
        )

    async def after_find(self, obj: Any) -> None:
        """Convert category from DB string to int for IntegerEnumField display.

        This ensures the dropdown shows the correct selected value in the admin UI.
        """
        import logging

        logger = logging.getLogger(__name__)

        # Convert DB string to API integer for display
        if hasattr(obj, "category") and obj.category:
            db_value = obj.category
            api_enum = PROFILE_CATEGORY_DB_TO_API.get(db_value)
            if api_enum:
                obj.category = api_enum.value
                logger.info(
                    f"[AIProfileTemplate after_find] Converted category from '{db_value}' to {obj.category}"
                )
            else:
                logger.warning(f"[AIProfileTemplate after_find] Unknown category value: {db_value}")
        else:
            logger.info(
                f"[AIProfileTemplate after_find] obj.id: {getattr(obj, 'id', None)}, category is None or empty"
            )

        return None

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["qiao_id", "nickname", "category"]
    sortable_fields = [
        "id",
        "qiao_id",
        "category",
        "nickname",
        "gender",
        "status",
        "is_reusable",
        "created_at",
        "updated_at",
    ]

    fields = [
        StringField("id", label="ID", help_text="Internal profile template ID"),
        StringField("qiao_id", label="Qiao ID", help_text="External external identifier for this template"),
        CategoryEnumField(
            "category",
            enum=AIProfileCategory,
            db_to_api_map=PROFILE_CATEGORY_DB_TO_API,
            api_to_db_map=PROFILE_CATEGORY_API_TO_DB,
            label="Category",
            help_text="Profile template category (交友/恋爱/倾诉/闺蜜/同好)",
            required=False,
        ),
        HasOne(
            "character_template",
            identity="ai_character_template",
            label="Character Template",
            help_text="Associated AI character template",
            required=True,
        ),
        _CharacterTemplateDisplayNameField(),
        StringField("nickname", label="Nickname", help_text="Character nickname"),
        IntegerEnumField(
            "gender", enum=Gender, label="Gender", help_text="Character gender (optional)", required=False
        ),
        StringField("avatar_url", label="Avatar URL", help_text="Character avatar image URL"),
        TextAreaField("bio", label="Bio", help_text="Character biography and description"),
        StringField("region", label="Region", help_text="Character location/region"),
        IntegerEnumField(
            "is_reusable",
            enum=ReusableStatus,
            label="Reusable",
            help_text="Whether this template can be used multiple times",
            required=True,
        ),
        IntegerEnumField(
            "status",
            enum=AIStyleStatus,
            label="Status",
            help_text="Active templates can be used",
            required=True,
        ),
        LocalDateTimeField("created_at", label="Created At"),
        LocalDateTimeField("updated_at", label="Updated At"),
    ]


# Create view instances
ai_character_template_view = AICharacterTemplateView(
    AICharacterTemplate,
    name="AI Character Templates",
    label="Character Templates",
    icon="fa fa-file-text",
    identity="ai_character_template",
)

ai_profile_template_view = AIProfileTemplateView(
    AIProfileTemplate,
    name="AI Profile Templates",
    label="Profile Templates",
    icon="fa fa-file-user",
    identity="ai_profile_template",
)

# Export template views
AI_TEMPLATE_VIEWS = [
    ai_character_template_view,
    ai_profile_template_view,
]
