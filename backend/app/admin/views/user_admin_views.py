"""
User and admin-related model views for Starlette-Admin.
Creates ModelView instances for user management and admin system models.
"""

from starlette_admin.contrib.sqla import ModelView
from starlette_admin import EnumField, HasOne, StringField, TextAreaField

# Import user and admin models
from models.admin import AdminUser, AdminOperationLog, AdminLoginLog
from models.user import User
from models.profile import Profile
from models.contact import Contact

# Import enums
from enums import (
    UserStatus,
    UserType,
    AdminRole,
    AdminStatus,
    Gender,
    ProfileOwnerType,
    ContactType,
    AICharacterCreator,
)


class AdminUserView(ModelView):
    """Enhanced AdminUser view with proper field configuration."""

    def can_delete(self, request):
        return False

    fields = [
        StringField("username", label="Username", help_text="Administrator username"),
        EnumField("role", enum=AdminRole, label="Role", help_text="Administrator role level"),
        EnumField("status", enum=AdminStatus, label="Status", help_text="Account status"),
        "last_login",
        "login_count",
        "created_by",
        "created_at",
        "updated_at",
    ]
    fields_default_sort = [("created_at", True)]
    searchable_fields = ["username"]
    sortable_fields = ["id", "username", "role", "status", "created_at", "last_login"]
    exclude_fields_from_list = ["password_hash"]
    exclude_fields_from_detail = ["password_hash"]
    exclude_fields_from_create = [
        "id",
        "created_at",
        "updated_at",
        "last_login",
        "login_count",
        "created_by",
    ]
    exclude_fields_from_edit = ["id", "created_at", "updated_at", "last_login", "login_count", "created_by"]


class AdminOperationLogView(ModelView):
    """Enhanced Admin Operation Log view - read-only for monitoring."""

    can_create = False
    can_edit = False

    def can_delete(self, request):
        return False

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["resource_name", "operation_desc"]
    sortable_fields = ["id", "admin_user_id", "operation_type", "resource_type", "created_at"]


class AdminLoginLogView(ModelView):
    """Enhanced Admin Login Log view - read-only for monitoring."""

    can_create = False
    can_edit = False

    def can_delete(self, request):
        return False

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["username", "ip_address"]
    sortable_fields = ["id", "admin_user_id", "username", "result", "created_at"]


class UserView(ModelView):
    """Enhanced User view with proper field configuration."""

    def can_delete(self, request):
        return False

    exclude_fields_from_create = ["id", "qiao_id", "created_at", "updated_at", "last_login"]
    exclude_fields_from_edit = ["id", "qiao_id", "created_at", "updated_at", "last_login"]
    exclude_fields_from_list = ["password_hash", "wechat_openid", "apple_id"]
    exclude_fields_from_detail = ["password_hash"]

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["username", "phone", "email", "qiao_id"]
    sortable_fields = ["id", "username", "qiao_id", "status", "user_type", "created_at", "last_login"]

    fields = [
        "qiao_id",
        StringField("username", label="Username", help_text="Display name for the user"),
        StringField("phone", label="Phone Number", help_text="Phone number for login"),
        StringField("email", label="Email Address", help_text="Email address for notifications"),
        EnumField("status", enum=UserStatus, label="Account Status", help_text="Current account status"),
        EnumField("user_type", enum=UserType, label="User Type", help_text="User classification"),
        "last_login",
        "created_at",
        "updated_at",
    ]


class ProfileView(ModelView):
    """Enhanced Profile view with proper field configuration."""

    exclude_fields_from_create = ["id", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "created_at", "updated_at"]

    def can_delete(self, request):
        return False

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["nickname", "owner_qiao_id"]
    sortable_fields = ["id", "owner_type", "nickname", "gender", "created_at"]

    fields = [
        "owner_id",
        StringField(
            "owner_qiao_id", label="Owner External ID", help_text="External ID of the profile owner"
        ),
        EnumField(
            "owner_type", enum=ProfileOwnerType, label="Owner Type", help_text="Type of profile owner"
        ),
        StringField("nickname", label="Nickname", help_text="Display nickname"),
        EnumField("gender", enum=Gender, label="Gender", help_text="Gender information"),
        HasOne(
            "avatar_file_id",
            identity="media_file",
            label="Avatar File",
            help_text="Select avatar file from media library",
        ),
        StringField("avatar_url", label="Avatar URL", help_text="Profile avatar image URL"),
        TextAreaField(
            "avatar_prompt", label="Avatar Prompt", help_text="Description for AI-generated avatars"
        ),
        TextAreaField("bio", label="Bio", help_text="Profile biography"),
        StringField("region", label="Region", help_text="Location/region information"),
    ]


class ContactView(ModelView):
    """Enhanced Contact view with proper field configuration."""

    exclude_fields_from_create = ["id", "conv_id", "created_at", "updated_at", "deleted_at"]
    exclude_fields_from_edit = ["id", "conv_id", "created_at", "updated_at", "deleted_at"]
    exclude_fields_from_list = ["tags", "remark"]

    def can_delete(self, request):
        return False

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["conv_id", "user_qiao_id", "contact_qiao_id", "alias"]
    sortable_fields = ["id", "contact_type", "alias", "is_pinned", "is_muted", "is_blocked", "created_at"]

    fields = [
        StringField("conv_id", label="Conversation ID", help_text="Unique conversation identifier"),
        HasOne(
            "user_id",
            identity="user",
            label="Owner User",
            help_text="Select the user who owns this contact",
        ),
        StringField("user_qiao_id", label="User External ID", help_text="Owner user external ID"),
        EnumField("contact_type", enum=ContactType, label="Contact Type", help_text="Type of contact"),
        "contact_id",
        StringField("contact_qiao_id", label="Contact External ID", help_text="Contact external ID"),
        StringField("alias", label="Alias", help_text="Custom name for this contact"),
        StringField("avatar_alias_url", label="Custom Avatar", help_text="Custom avatar URL"),
        "tags",
        TextAreaField("remark", label="Remark", help_text="Additional notes about this contact"),
        EnumField(
            "is_pinned",
            choices=[(0, "No"), (1, "Yes")],
            label="Pinned",
            help_text="Pin to top of contact list",
        ),
        EnumField(
            "is_muted", choices=[(0, "No"), (1, "Yes")], label="Muted", help_text="Mute notifications"
        ),
        EnumField(
            "is_blocked", choices=[(0, "No"), (1, "Yes")], label="Blocked", help_text="Block this contact"
        ),
        EnumField(
            "is_deleted", choices=[(0, "No"), (1, "Yes")], label="Deleted", help_text="Soft delete status"
        ),
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
contact_view = ContactView(Contact, name="Contacts", icon="fa fa-address-book", identity="contact")

# Export all user and admin views
USER_ADMIN_MODEL_VIEWS = [
    admin_user_view,
    admin_operation_log_view,
    admin_login_log_view,
    user_view,
    profile_view,
    contact_view,
]