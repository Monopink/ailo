"""
User and admin-related model views for Starlette-Admin.
Creates ModelView instances for user management and admin system models.
"""

from typing import Dict, Any
from starlette.requests import Request
from starlette_admin.contrib.sqla import ModelView
from .base import BaseRoleAwareModelView
from starlette_admin import StringField, TextAreaField, HasOne
from admin.views.base import IntegerEnumField
from starlette_admin.exceptions import FormValidationError

# Import user and admin models
from models.admin import AdminUser, AdminOperationLog, AdminLoginLog
from models.user import User
from models.profile import Profile, UserProfileLog
from models.contact import Contact

# Import enums
from enums import (
    UserStatus,
    UserType,
    AdminRole,
    AdminStatus,
    Gender,
    ProfileOwnerType,
    ProfileModifierType,
    ContactType,
)


class AdminUserView(BaseRoleAwareModelView):
    """Enhanced AdminUser view with proper field configuration."""

    def can_delete(self, request):
        return False

    def can_create(self, request):  # type: ignore[override]
        from enums import AdminRole
        admin_user = request.session.get("admin_user") if hasattr(request, "session") else None
        role = admin_user.get("role") if admin_user else None
        try:
            role_val = int(role) if role is not None else None
        except Exception:
            role_val = None
        return role_val == AdminRole.SUPER_ADMIN

    def can_edit(self, request):  # type: ignore[override]
        from enums import AdminRole
        admin_user = request.session.get("admin_user") if hasattr(request, "session") else None
        role = admin_user.get("role") if admin_user else None
        try:
            role_val = int(role) if role is not None else None
        except Exception:
            role_val = None
        return role_val == AdminRole.SUPER_ADMIN

    fields = [
        StringField("username", label="Username", help_text="Administrator username", required=True),
        StringField(
            "password",
            label="Password",
            help_text="Administrator password (plain text, leave blank to keep current password when editing)",
            required=False,
        ),
        IntegerEnumField(
            "role",
            enum=AdminRole,
            label="Role",
            help_text="Administrator role level (required selection: Super Admin, Admin, or Viewer)",
            required=True,
        ),
        IntegerEnumField(
            "status",
            enum=AdminStatus,
            label="Status",
            help_text="Account status (default: Active)",
            required=True,
        ),
        "last_login",
        "login_count",
        "created_by",
        "created_at",
        "updated_at",
    ]
    fields_default_sort = [("created_at", True)]
    searchable_fields = ["username"]
    sortable_fields = ["id", "username", "role", "status", "created_at", "last_login"]
    exclude_fields_from_list = ["password_hash", "password"]
    exclude_fields_from_detail = ["password_hash", "password"]
    exclude_fields_from_create = [
        "id",
        "password_hash",
        "created_at",
        "updated_at",
        "last_login",
        "login_count",
        "created_by",
    ]
    exclude_fields_from_edit = [
        "id",
        "password_hash",
        "created_at",
        "updated_at",
        "last_login",
        "login_count",
        "created_by",
    ]

    async def validate(self, request: Request, data: Dict[str, Any]) -> None:
        """Validate admin user data."""
        password = data.get("password")

        # For create operation, password is required
        if request.url.path.endswith("/create"):
            if not password:
                raise FormValidationError({"password": "Password is required when creating admin user"})

        # Validate password length if provided
        if password and len(password) < 8:
            raise FormValidationError({"password": "Password must be at least 8 characters long"})

        await super().validate(request, data)

    async def before_create(self, request: Request, data: Dict[str, Any], obj: Any) -> None:
        """Hash password before creating admin user."""
        from core.security import get_password_hash

        password = data.pop("password", None)

        if password:
            obj.password_hash = get_password_hash(password)

    async def before_edit(self, request: Request, data: Dict[str, Any], obj: Any) -> None:
        """Hash password before updating admin user if password is changed."""
        from core.security import get_password_hash

        password = data.pop("password", None)

        # Only update password if a new one is provided
        if password:
            obj.password_hash = get_password_hash(password)


class AdminOperationLogView(ModelView):
    """Enhanced Admin Operation Log view - read-only for monitoring."""

    def can_create(self, request):
        return False

    def can_edit(self, request):
        return False

    def can_delete(self, request):
        return False

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["resource_name", "operation_desc"]
    sortable_fields = ["id", "admin_user_id", "resource_type", "created_at"]

    fields = [
        "id",
        "admin_user_id",
        StringField("operation_type_display", label="Operation Type"),
        "resource_type",
        "resource_id",
        "resource_name",
        "operation_desc",
        "ip_address",
        "user_agent",
        "created_at",
    ]

    exclude_fields_from_create = ["operation_type_display"]
    exclude_fields_from_edit = ["operation_type_display"]


class AdminLoginLogView(ModelView):
    """Enhanced Admin Login Log view - read-only for monitoring."""

    def can_create(self, request):
        return False

    def can_edit(self, request):
        return False

    def can_delete(self, request):
        return False

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["username", "ip_address"]
    sortable_fields = ["id", "admin_user_id", "username", "result", "created_at"]


class UserView(BaseRoleAwareModelView):
    """Enhanced User view with proper field configuration."""

    def can_delete(self, request):
        return False

    exclude_fields_from_create = [
        "id",
        "qiao_id",
        "password_hash",
        "created_at",
        "updated_at",
        "last_login",
    ]
    exclude_fields_from_edit = ["id", "qiao_id", "password_hash", "created_at", "updated_at", "last_login"]
    exclude_fields_from_list = ["password_hash", "password", "wechat_openid", "apple_id"]
    exclude_fields_from_detail = ["password_hash", "password"]

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["username", "phone", "email", "qiao_id"]
    sortable_fields = ["id", "username", "qiao_id", "status", "user_type", "created_at", "last_login"]

    fields = [
        StringField("id", label="ID", help_text="Internal user ID"),
        StringField("qiao_id", label="Qiao ID", help_text="External user identifier"),
        StringField("username", label="Username", help_text="Display name for the user"),
        StringField("phone", label="Phone Number", help_text="Phone number for login"),
        StringField("email", label="Email Address", help_text="Email address for notifications"),
        StringField(
            "password",
            label="Password",
            help_text="⚠️ Leave blank to keep current password unchanged. Enter new password (min 8 characters) to change.",
            required=False,
        ),
        IntegerEnumField(
            "status",
            enum=UserStatus,
            label="Account Status",
            help_text="Current account status (default: Active)",
            required=True,
        ),
        IntegerEnumField(
            "user_type",
            enum=UserType,
            label="User Type",
            help_text="User classification (default: Normal)",
            required=True,
        ),
        "last_login",
        "created_at",
        "updated_at",
    ]

    async def validate(self, request: Request, data: Dict[str, Any]) -> None:
        """Validate user data."""
        password = data.get("password")

        # For create operation, password is required
        if request.url.path.endswith("/create"):
            if not password:
                raise FormValidationError({"password": "Password is required when creating user"})

        # Validate password length if provided
        if password and len(password) < 8:
            raise FormValidationError({"password": "Password must be at least 8 characters long"})

        await super().validate(request, data)

    async def before_create(self, request: Request, data: Dict[str, Any], obj: Any) -> None:
        """Hash password before creating user."""
        from core.security import get_password_hash

        password = data.pop("password", None)

        if password:
            obj.password_hash = get_password_hash(password)

    async def before_edit(self, request: Request, data: Dict[str, Any], obj: Any) -> None:
        """Hash password before updating user if password is changed."""
        from core.security import get_password_hash

        password = data.pop("password", None)

        # Only update password if a new one is provided
        if password:
            obj.password_hash = get_password_hash(password)


class ProfileView(BaseRoleAwareModelView):
    """Enhanced Profile view with proper field configuration."""

    # Exclude auto-filled fields from create/edit
    exclude_fields_from_create = [
        "id",
        "owner_id",  # Auto-filled
        "owner_qiao_id",  # Auto-filled
        "owner_type",  # Auto-inferred from selected owner
        "created_at",
        "updated_at",
    ]
    exclude_fields_from_edit = [
        "id",
        "owner_id",  # Auto-filled
        "owner_qiao_id",  # Auto-filled
        "owner_type",  # Auto-inferred from selected owner
        "created_at",
        "updated_at",
    ]

    def can_delete(self, request):
        return False

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["nickname", "owner_qiao_id"]
    sortable_fields = ["id", "owner_type", "nickname", "gender", "created_at"]

    fields = [
        StringField("id", label="ID", help_text="Internal profile ID"),
        # Polymorphic owner fields - select one, owner_type is auto-inferred
        HasOne(
            "_owner_user",
            identity="user",
            label="Owner (User)",
            help_text="Select a user (includes all user types: normal, official, virtual)",
            required=False,
        ),
        HasOne(
            "_owner_character",
            identity="ai_character",
            label="Owner (AI Character)",
            help_text="Select an AI character",
            required=False,
        ),
        StringField("owner_qiao_id", label="Owner Qiao ID", help_text="External ID of the profile owner"),
        StringField("nickname", label="Nickname", help_text="Display nickname"),
        IntegerEnumField("gender", enum=Gender, label="Gender", help_text="Gender information"),
        StringField(
            "avatar_file_id", label="Avatar File ID", help_text="Avatar file ID from media library"
        ),
        StringField("avatar_url", label="Avatar URL", help_text="Profile avatar image URL"),
        TextAreaField(
            "avatar_prompt", label="Avatar Prompt", help_text="Description for AI-generated avatars"
        ),
        TextAreaField("bio", label="Bio", help_text="Profile biography"),
        StringField("region", label="Region", help_text="Location/region information"),
    ]

    async def validate(self, request: Request, data: Dict[str, Any]) -> None:
        """Custom validation for polymorphic owner fields."""
        owner_user = data.get("_owner_user")
        owner_character = data.get("_owner_character")

        # Must select exactly one owner
        if not owner_user and not owner_character:
            raise FormValidationError(
                {"_owner_user": "Please select either Owner (User) or Owner (AI Character)"}
            )
        if owner_user and owner_character:
            raise FormValidationError({"_owner_user": "Please select only one owner"})

    async def before_create(self, request: Request, data: Dict[str, Any], obj: Any) -> None:
        """Set auto-filled fields before database commit."""
        from models.user import User
        from models.ai.character import AICharacter
        from models.profile import Profile
        from sqlalchemy import select
        from starlette_admin.exceptions import FormValidationError

        # Convert empty string to None for integer fields FIRST (before any database operations)
        if obj.avatar_file_id == "":
            obj.avatar_file_id = None

        # Auto-infer owner_type and fill owner_id, owner_qiao_id
        owner_user = data.get("_owner_user")
        owner_character = data.get("_owner_character")

        if owner_user and isinstance(owner_user, User):
            obj.owner_type = ProfileOwnerType.USER
            obj.owner_id = owner_user.id
            obj.owner_qiao_id = owner_user.qiao_id
        elif owner_character and isinstance(owner_character, AICharacter):
            obj.owner_type = ProfileOwnerType.AI
            obj.owner_id = owner_character.id
            obj.owner_qiao_id = owner_character.qiao_id

        # Check for duplicate profile (use no_autoflush to prevent premature flush)
        session = request.state.session
        with session.no_autoflush:
            stmt = select(Profile).where(
                Profile.owner_qiao_id == obj.owner_qiao_id, Profile.owner_type == obj.owner_type
            )
            result = await session.execute(stmt)
            existing_profile = result.scalar_one_or_none()
            if existing_profile:
                field_name = (
                    "_owner_user" if obj.owner_type == ProfileOwnerType.USER else "_owner_character"
                )
                raise FormValidationError(
                    {field_name: f"Profile already exists for this owner (ID: {existing_profile.id})"}
                )

    async def before_edit(self, request: Request, data: Dict[str, Any], obj: Any) -> None:
        """Set auto-filled fields before database commit."""
        from models.user import User
        from models.ai.character import AICharacter

        # Convert empty string to None for integer fields
        if obj.avatar_file_id == "":
            obj.avatar_file_id = None

        # Auto-infer owner_type and fill owner_id, owner_qiao_id
        owner_user = data.get("_owner_user")
        owner_character = data.get("_owner_character")

        if owner_user and isinstance(owner_user, User):
            obj.owner_type = ProfileOwnerType.USER
            obj.owner_id = owner_user.id
            obj.owner_qiao_id = owner_user.qiao_id
        elif owner_character and isinstance(owner_character, AICharacter):
            obj.owner_type = ProfileOwnerType.AI
            obj.owner_id = owner_character.id
            obj.owner_qiao_id = owner_character.qiao_id


class ContactView(BaseRoleAwareModelView):
    """Enhanced Contact view with proper field configuration."""

    # Exclude auto-filled fields from create/edit
    exclude_fields_from_create = [
        "id",
        "conv_id",  # Auto-generated
        "user_id",  # Auto-filled
        "user_qiao_id",  # Auto-filled
        "contact_type",  # Auto-inferred from selected contact
        "contact_id",  # Auto-filled
        "contact_qiao_id",  # Auto-filled
        "created_at",
        "updated_at",
        "deleted_at",
    ]
    exclude_fields_from_edit = [
        "id",
        "conv_id",  # Auto-generated
        "user_id",  # Auto-filled
        "user_qiao_id",  # Auto-filled
        "contact_type",  # Auto-inferred from selected contact
        "contact_id",  # Auto-filled
        "contact_qiao_id",  # Auto-filled
        "created_at",
        "updated_at",
        "deleted_at",
    ]
    exclude_fields_from_list = ["tags", "remark"]

    def can_delete(self, request):
        return False

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["conv_id", "user_qiao_id", "contact_qiao_id", "alias"]
    sortable_fields = ["id", "contact_type", "alias", "is_pinned", "is_muted", "is_blocked", "created_at"]

    fields = [
        StringField("id", label="ID", help_text="Internal contact ID"),
        StringField("conv_id", label="Conversation ID", help_text="Unique conversation identifier"),
        HasOne(
            "user",
            identity="user",
            label="Owner User",
            help_text="User who owns this contact",
            required=False,
        ),
        StringField("user_qiao_id", label="User Qiao ID", help_text="Owner user external ID"),
        # Polymorphic contact fields - select one, contact_type is auto-inferred
        HasOne(
            "_contact_user",
            identity="user",
            label="Contact (User)",
            help_text="Select a user as contact",
            required=False,
        ),
        HasOne(
            "_contact_character",
            identity="ai_character",
            label="Contact (AI Character)",
            help_text="Select an AI character as contact",
            required=False,
        ),
        StringField("contact_qiao_id", label="Contact Qiao ID", help_text="Contact external ID"),
        StringField("alias", label="Alias", help_text="Custom name for this contact"),
        StringField("avatar_alias_url", label="Custom Avatar", help_text="Custom avatar URL"),
        "tags",
        TextAreaField("remark", label="Remark", help_text="Additional notes about this contact"),
        IntegerEnumField(
            "is_pinned",
            choices=[(0, "No"), (1, "Yes")],
            label="Pinned",
            help_text="Pin to top of contact list (default: No)",
            required=True,
        ),
        IntegerEnumField(
            "is_muted",
            choices=[(0, "No"), (1, "Yes")],
            label="Muted",
            help_text="Mute notifications (default: No)",
            required=True,
        ),
        IntegerEnumField(
            "is_blocked",
            choices=[(0, "No"), (1, "Yes")],
            label="Blocked",
            help_text="Block this contact (default: No)",
            required=True,
        ),
        IntegerEnumField(
            "is_deleted",
            choices=[(0, "No"), (1, "Yes")],
            label="Deleted",
            help_text="Soft delete status (default: No)",
            required=True,
        ),
    ]

    async def validate(self, request: Request, data: Dict[str, Any]) -> None:
        """Custom validation for polymorphic contact fields."""
        contact_user = data.get("_contact_user")
        contact_character = data.get("_contact_character")

        # Must select exactly one contact
        if not contact_user and not contact_character:
            raise FormValidationError(
                {"_contact_user": "Please select either Contact (User) or Contact (AI Character)"}
            )
        if contact_user and contact_character:
            raise FormValidationError({"_contact_user": "Please select only one contact"})

    async def before_create(self, request: Request, data: Dict[str, Any], obj: Any) -> None:
        """Set auto-filled fields before database commit."""
        import secrets
        import string
        from sqlalchemy import select
        from models.user import User
        from models.ai.character import AICharacter
        from models.contact import Contact
        from starlette_admin.exceptions import FormValidationError

        # Auto-fill user_qiao_id from selected user
        user = data.get("user")
        if user and isinstance(user, User):
            obj.user_id = user.id
            obj.user_qiao_id = user.qiao_id

        # Auto-infer contact_type and fill contact_id, contact_qiao_id
        contact_user = data.get("_contact_user")
        contact_character = data.get("_contact_character")

        if contact_user and isinstance(contact_user, User):
            obj.contact_type = ContactType.USER
            obj.contact_id = contact_user.id
            obj.contact_qiao_id = contact_user.qiao_id
        elif contact_character and isinstance(contact_character, AICharacter):
            obj.contact_type = ContactType.AI
            obj.contact_id = contact_character.id
            obj.contact_qiao_id = contact_character.qiao_id

        # Validate and handle conv_id generation with reverse contact checking
        session = request.state.session
        errors = {}

        if obj.user_id and obj.contact_id and obj.contact_type:
            with session.no_autoflush:
                # Check for duplicate contact (same user + contact)
                duplicate_stmt = select(Contact).where(
                    Contact.user_id == obj.user_id,
                    Contact.contact_id == obj.contact_id,
                    Contact.contact_type == obj.contact_type,
                )
                duplicate_result = await session.execute(duplicate_stmt)
                existing_contact = duplicate_result.scalar_one_or_none()
                if existing_contact:
                    errors["_contact_user" if obj.contact_type == ContactType.USER else "_contact_character"] = (
                        f"Contact already exists for this user (ID: {existing_contact.id}). "
                        f"Each user can only have one contact record per contact."
                    )

                # Check for reverse contact (contact → user) to reuse conv_id
                # Only check reverse if contact is a User (user-to-user relationship)
                if obj.contact_type == ContactType.USER:
                    reverse_stmt = select(Contact).where(
                        Contact.user_id == obj.contact_id,  # Reversed: contact as user
                        Contact.contact_id == obj.user_id,  # Reversed: user as contact
                        Contact.contact_type == ContactType.USER,
                    )
                    reverse_result = await session.execute(reverse_stmt)
                    reverse_contact = reverse_result.scalar_one_or_none()

                    if reverse_contact:
                        # Reuse conv_id from reverse contact
                        obj.conv_id = reverse_contact.conv_id
                    else:
                        # Generate new conv_id
                        random_chars = "".join(
                            secrets.choice(string.ascii_letters + string.digits) for _ in range(16)
                        )
                        obj.conv_id = f"conv_{random_chars}"
                else:
                    # For AI contacts, always generate new conv_id (no reverse relationship)
                    random_chars = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))
                    obj.conv_id = f"conv_{random_chars}"

        if errors:
            raise FormValidationError(errors)

    async def before_edit(self, request: Request, data: Dict[str, Any], obj: Any) -> None:
        """Set auto-filled fields before database commit."""
        from models.user import User
        from models.ai.character import AICharacter

        # Auto-fill user_qiao_id from selected user
        user = data.get("user")
        if user and isinstance(user, User):
            obj.user_id = user.id
            obj.user_qiao_id = user.qiao_id

        # Auto-infer contact_type and fill contact_id, contact_qiao_id
        contact_user = data.get("_contact_user")
        contact_character = data.get("_contact_character")

        if contact_user and isinstance(contact_user, User):
            obj.contact_type = ContactType.USER
            obj.contact_id = contact_user.id
            obj.contact_qiao_id = contact_user.qiao_id
        elif contact_character and isinstance(contact_character, AICharacter):
            obj.contact_type = ContactType.AI
            obj.contact_id = contact_character.id
            obj.contact_qiao_id = contact_character.qiao_id


class UserProfileLogView(ModelView):
    """User Profile Log view for viewing profile change history."""

    label = "Profile Logs"
    name = "Profile Logs"

    # Read-only view
    def can_create(self, request):
        return False

    def can_edit(self, request):
        return False

    def can_delete(self, request):
        return False

    exclude_fields_from_create = [
        "id",
        "owner_id",
        "owner_qiao_id",
        "owner_type",
        "modified_by_type",
        "field_name",
        "old_value",
        "new_value",
        "change_reason",
        "created_at",
    ]
    exclude_fields_from_edit = [
        "id",
        "owner_id",
        "owner_qiao_id",
        "owner_type",
        "modified_by_type",
        "field_name",
        "old_value",
        "new_value",
        "change_reason",
        "created_at",
    ]

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["owner_qiao_id", "field_name"]
    sortable_fields = [
        "id",
        "owner_qiao_id",
        "owner_type",
        "modified_by_type",
        "field_name",
        "created_at",
    ]

    fields = [
        StringField("id", label="ID", help_text="Internal log ID"),
        StringField("owner_id", label="Owner ID", help_text="Owner internal ID"),
        StringField("owner_qiao_id", label="Owner Qiao ID", help_text="Owner external ID"),
        IntegerEnumField(
            "owner_type",
            enum=ProfileOwnerType,
            label="Owner Type",
            help_text="Owner type: 1=user, 2=ai, 3=official",
        ),
        IntegerEnumField(
            "modified_by_type",
            enum=ProfileModifierType,
            label="Modified By",
            help_text="Modifier type: 1=user, 2=admin, 3=system",
        ),
        StringField("field_name", label="Field Name", help_text="Modified field name"),
        TextAreaField("old_value", label="Old Value", help_text="Old value"),
        TextAreaField("new_value", label="New Value", help_text="New value"),
        StringField("change_reason", label="Change Reason", help_text="Reason for change"),
        "created_at",
    ]


# Create view instances
admin_user_view = AdminUserView(AdminUser, name="Admin Users", icon="fa fa-users", identity="admin_user")
admin_operation_log_view = AdminOperationLogView(
    AdminOperationLog, name="Operation Logs", icon="fa fa-list", identity="admin_operation_log"
)
admin_login_log_view = AdminLoginLogView(
    AdminLoginLog, name="Login Logs", icon="fa fa-sign-in", identity="admin_login_log"
)
user_view = UserView(User, name="Users", icon="fa fa-user", identity="user")
profile_view = ProfileView(Profile, name="Profiles", icon="fa fa-id-card", identity="profile")
user_profile_log_view = UserProfileLogView(
    UserProfileLog, name="Profile Logs", icon="fa fa-history", identity="user_profile_log"
)
contact_view = ContactView(Contact, name="Contacts", icon="fa fa-address-book", identity="contact")

# Export all user and admin views
USER_ADMIN_MODEL_VIEWS = [
    admin_user_view,
    admin_operation_log_view,
    admin_login_log_view,
    user_view,
    profile_view,
    user_profile_log_view,
    contact_view,
]
