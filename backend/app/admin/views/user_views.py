"""
User-related model views for Starlette-Admin.
Creates ModelView instances for user management and admin system models.
"""

import secrets
import string
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import desc, select
from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette_admin import CustomView, HasOne, IntegerField, JSONField, StringField, TextAreaField
from starlette_admin.actions import link_row_action
from starlette_admin.contrib.sqla import ModelView
from starlette_admin.exceptions import FormValidationError

from app.admin.fields import LocalDateTimeField
from app.admin.views.base import IntegerEnumField, convert_empty_strings_to_none
from app.core.security import get_password_hash
from app.enums import (
    ContactRequestSource,
    ContactRequestStatus,
    ContactType,
    Gender,
    ProfileModifierType,
    ProfileOwnerType,
    UserStatus,
    UserType,
)
from app.models.ai.instance import AIInstance
from app.models.ai.template import AIPersona
from app.models.contact import Contact, ContactRequest
from app.models.profile import Profile, UserProfileLog
from app.models.user import User
from app.services.contact.request_service import retry_pending_contact_request
from app.services.system_config import get_config

from .base import BaseRoleAwareModelView


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
    exclude_fields_from_edit = [
        "id",
        "qiao_id",
        "password_hash",
        "created_at",
        "updated_at",
        "last_login",
    ]
    exclude_fields_from_list = ["password_hash", "password"]
    exclude_fields_from_detail = ["password_hash", "password"]

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["username", "phone", "email", "qiao_id"]
    sortable_fields = [
        "id",
        "username",
        "qiao_id",
        "status",
        "user_type",
        "created_at",
        "updated_at",
        "last_login",
    ]

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
            "is_verified",
            choices=[(0, "No"), (1, "Yes")],
            label="Verified",
            help_text="Real-name verification status",
            required=True,
        ),
        StringField(
            "verify_source", label="Verify Source", help_text="Verification source/provider"
        ),
        TextAreaField(
            "verification_info",
            label="Verification Info",
            help_text="Verification extra information (JSON/text)",
        ),
        LocalDateTimeField(
            "verified_at", label="Verified At", help_text="Verification approval time"
        ),
        IntegerEnumField(
            "user_type",
            enum=UserType,
            label="User Type",
            help_text="User classification (default: Normal)",
            required=True,
        ),
        LocalDateTimeField("last_login", label="Last Login", help_text="Last login time"),
        LocalDateTimeField("created_at", label="Created At", help_text="Account creation time"),
        LocalDateTimeField("updated_at", label="Updated At", help_text="Last update time"),
    ]

    async def validate(self, request: Request, data: dict[str, Any]) -> None:
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

    async def before_create(self, request: Request, data: dict[str, Any], obj: Any) -> None:
        """Hash password before creating user. Convert empty unique fields to NULL."""
        password = data.pop("password", None)

        if password:
            obj.password_hash = get_password_hash(password)

        # Convert empty unique fields to NULL to avoid unique constraint violation
        convert_empty_strings_to_none(obj, ["phone", "email"])

    async def before_edit(self, request: Request, data: dict[str, Any], obj: Any) -> None:
        """Hash password before updating user if password is changed. Convert empty unique fields to NULL."""
        password = data.pop("password", None)

        # Only update password if a new one is provided
        if password:
            obj.password_hash = get_password_hash(password)

        # Convert empty unique fields to NULL to avoid unique constraint violation
        convert_empty_strings_to_none(obj, ["phone", "email"])


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
    sortable_fields = ["id", "owner_type", "nickname", "gender", "created_at", "updated_at"]

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
            "_owner_persona",
            identity="ai_persona",
            label="Owner (AI Persona)",
            help_text="Select an AI persona",
            required=False,
        ),
        HasOne(
            "_owner_instance",
            identity="ai_instance",
            label="Owner (AI Instance)",
            help_text="Select an AI instance",
            required=False,
        ),
        StringField(
            "owner_qiao_id", label="Owner Qiao ID", help_text="External ID of the profile owner"
        ),
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
        LocalDateTimeField("created_at", label="Created At", help_text="Profile creation time"),
        LocalDateTimeField("updated_at", label="Updated At", help_text="Last update time"),
    ]

    async def validate(self, request: Request, data: dict[str, Any]) -> None:
        """Custom validation for polymorphic owner fields."""
        owner_user = data.get("_owner_user")
        owner_persona = data.get("_owner_persona")
        owner_instance = data.get("_owner_instance")

        # Must select exactly one owner
        selected_count = sum([bool(owner_user), bool(owner_persona), bool(owner_instance)])
        if selected_count == 0:
            raise FormValidationError(
                {"_owner_user": "Please select one owner: User, AI Persona, or AI Instance"}
            )
        if selected_count > 1:
            raise FormValidationError({"_owner_user": "Please select only one owner"})

    async def before_create(self, request: Request, data: dict[str, Any], obj: Any) -> None:
        """Set auto-filled fields before database commit."""
        # Convert empty string to None for integer fields FIRST (before any database operations)
        if obj.avatar_file_id == "":
            obj.avatar_file_id = None

        # Auto-infer owner_type and fill owner_id, owner_qiao_id
        owner_user = data.get("_owner_user")
        owner_persona = data.get("_owner_persona")
        owner_instance = data.get("_owner_instance")

        if owner_user and isinstance(owner_user, User):
            obj.owner_type = ProfileOwnerType.USER
            obj.owner_id = owner_user.id
            obj.owner_qiao_id = owner_user.qiao_id
        elif owner_persona and isinstance(owner_persona, AIPersona):
            obj.owner_type = ProfileOwnerType.AI_PERSONA
            obj.owner_id = owner_persona.id
            obj.owner_qiao_id = owner_persona.qiao_id
        elif owner_instance and isinstance(owner_instance, AIInstance):
            obj.owner_type = ProfileOwnerType.AI_INSTANCE
            obj.owner_id = owner_instance.id
            obj.owner_qiao_id = owner_instance.qiao_id

        # Check for duplicate profile (use no_autoflush to prevent premature flush)
        session = request.state.session
        with session.no_autoflush:
            stmt = select(Profile).where(
                Profile.owner_qiao_id == obj.owner_qiao_id, Profile.owner_type == obj.owner_type
            )
            result = await session.execute(stmt)
            existing_profile = result.scalar_one_or_none()
            if existing_profile:
                if obj.owner_type == ProfileOwnerType.USER:
                    field_name = "_owner_user"
                elif obj.owner_type == ProfileOwnerType.AI_PERSONA:
                    field_name = "_owner_persona"
                else:
                    field_name = "_owner_instance"
                raise FormValidationError(
                    {
                        field_name: f"Profile already exists for this owner (ID: {existing_profile.id})"
                    }
                )

    async def before_edit(self, request: Request, data: dict[str, Any], obj: Any) -> None:
        """Set auto-filled fields before database commit."""
        # Convert empty string to None for integer fields
        if obj.avatar_file_id == "":
            obj.avatar_file_id = None

        # Auto-infer owner_type and fill owner_id, owner_qiao_id
        owner_user = data.get("_owner_user")
        owner_persona = data.get("_owner_persona")
        owner_instance = data.get("_owner_instance")

        if owner_user and isinstance(owner_user, User):
            obj.owner_type = ProfileOwnerType.USER
            obj.owner_id = owner_user.id
            obj.owner_qiao_id = owner_user.qiao_id
        elif owner_persona and isinstance(owner_persona, AIPersona):
            obj.owner_type = ProfileOwnerType.AI_PERSONA
            obj.owner_id = owner_persona.id
            obj.owner_qiao_id = owner_persona.qiao_id
        elif owner_instance and isinstance(owner_instance, AIInstance):
            obj.owner_type = ProfileOwnerType.AI_INSTANCE
            obj.owner_id = owner_instance.id
            obj.owner_qiao_id = owner_instance.qiao_id


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
    exclude_fields_from_list = []

    def can_delete(self, request):
        return False

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["conv_id", "user_qiao_id", "contact_qiao_id", "alias"]
    sortable_fields = [
        "id",
        "contact_type",
        "alias",
        "is_pinned",
        "is_muted",
        "is_blocked",
        "created_at",
        "updated_at",
        "deleted_at",
    ]

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
            "_contact_instance",
            identity="ai_instance",
            label="Contact (AI Instance)",
            help_text="Select an AI instance as contact",
            required=False,
        ),
        StringField("contact_qiao_id", label="Contact Qiao ID", help_text="Contact external ID"),
        StringField("alias", label="Alias", help_text="Custom name for this contact"),
        StringField("custom_avatar_url", label="Custom Avatar", help_text="Custom avatar URL"),
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
        LocalDateTimeField("created_at", label="Created At", help_text="Contact creation time"),
        LocalDateTimeField("updated_at", label="Updated At", help_text="Last update time"),
        LocalDateTimeField("deleted_at", label="Deleted At", help_text="Soft delete time"),
    ]

    async def validate(self, request: Request, data: dict[str, Any]) -> None:
        """Custom validation for polymorphic contact fields."""
        contact_user = data.get("_contact_user")
        contact_instance = data.get("_contact_instance")

        # Must select exactly one contact
        if not contact_user and not contact_instance:
            raise FormValidationError(
                {"_contact_user": "Please select either Contact (User) or Contact (AI Instance)"}
            )
        if contact_user and contact_instance:
            raise FormValidationError({"_contact_user": "Please select only one contact"})

    async def before_create(self, request: Request, data: dict[str, Any], obj: Any) -> None:
        """Set auto-filled fields before database commit."""
        # Auto-fill user_qiao_id from selected user
        user = data.get("user")
        if user and isinstance(user, User):
            obj.user_id = user.id
            obj.user_qiao_id = user.qiao_id

        # Auto-infer contact_type and fill contact_id, contact_qiao_id
        contact_user = data.get("_contact_user")
        contact_instance = data.get("_contact_instance")

        if contact_user and isinstance(contact_user, User):
            obj.contact_type = ContactType.USER
            obj.contact_id = contact_user.id
            obj.contact_qiao_id = contact_user.qiao_id
        elif contact_instance and isinstance(contact_instance, AIInstance):
            obj.contact_type = ContactType.AI
            obj.contact_id = contact_instance.id
            obj.contact_qiao_id = contact_instance.qiao_id

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
                    errors[
                        "_contact_user"
                        if obj.contact_type == ContactType.USER
                        else "_contact_instance"
                    ] = (
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
                    random_chars = "".join(
                        secrets.choice(string.ascii_letters + string.digits) for _ in range(16)
                    )
                    obj.conv_id = f"conv_{random_chars}"

        if errors:
            raise FormValidationError(errors)

    async def before_edit(self, request: Request, data: dict[str, Any], obj: Any) -> None:
        """Set auto-filled fields before database commit."""
        # Auto-fill user_qiao_id from selected user
        user = data.get("user")
        if user and isinstance(user, User):
            obj.user_id = user.id
            obj.user_qiao_id = user.qiao_id

        # Auto-infer contact_type and fill contact_id, contact_qiao_id
        contact_user = data.get("_contact_user")
        contact_instance = data.get("_contact_instance")

        if contact_user and isinstance(contact_user, User):
            obj.contact_type = ContactType.USER
            obj.contact_id = contact_user.id
            obj.contact_qiao_id = contact_user.qiao_id
        elif contact_instance and isinstance(contact_instance, AIInstance):
            obj.contact_type = ContactType.AI
            obj.contact_id = contact_instance.id
            obj.contact_qiao_id = contact_instance.qiao_id


class ContactRequestView(ModelView):
    """Enhanced Contact Request view for application management."""

    label = "Contact Requests"
    name = "Contact Requests"

    exclude_fields_from_create = [
        "id",
        "from_qiao_id",  # Auto-filled
        "from_type",  # Auto-inferred from selected from entity
        "from_id",  # Auto-filled
        "to_qiao_id",  # Auto-filled
        "to_type",  # Auto-inferred from selected to entity
        "to_id",  # Auto-filled
        "source",  # Auto-filled as ADMIN for admin panel creations
        "status",  # Auto-filled as PENDING
        "expires_at",  # Auto-calculated based on system config
        "created_at",
        "updated_at",
    ]
    exclude_fields_from_edit = [
        "id",
        "from_qiao_id",  # Auto-filled
        "from_type",  # Auto-inferred from selected from entity
        "from_id",  # Auto-filled
        "to_qiao_id",  # Auto-filled
        "to_type",  # Auto-inferred from selected to entity
        "to_id",  # Auto-filled
        "source",  # Cannot change source after creation
        "expires_at",  # Cannot change expiration after creation
        "created_at",
        "updated_at",
    ]
    exclude_fields_from_list = []

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["from_qiao_id", "to_qiao_id"]
    sortable_fields = [
        "id",
        "from_qiao_id",
        "to_qiao_id",
        "source",
        "status",
        "expires_at",
        "created_at",
        "updated_at",
    ]

    fields = [
        StringField("id", label="ID", help_text="Internal contact request ID"),
        # Polymorphic from fields - select one, from_type is auto-inferred
        HasOne(
            "_from_user",
            identity="user",
            label="From (User)",
            help_text="Select a user as applicant",
            required=False,
        ),
        HasOne(
            "_from_instance",
            identity="ai_instance",
            label="From (AI Instance)",
            help_text="Select an AI instance as applicant",
            required=False,
        ),
        StringField(
            "from_qiao_id", label="From Qiao ID", help_text="Applicant external identifier"
        ),
        # Polymorphic to fields - select one, to_type is auto-inferred
        HasOne(
            "_to_user",
            identity="user",
            label="To (User)",
            help_text="Select a user as target",
            required=False,
        ),
        HasOne(
            "_to_instance",
            identity="ai_instance",
            label="To (AI Instance)",
            help_text="Select an AI instance as target",
            required=False,
        ),
        StringField("to_qiao_id", label="To Qiao ID", help_text="Target external identifier"),
        IntegerEnumField(
            "source",
            enum=ContactRequestSource,
            label="Request Source",
            help_text="How the contact request was initiated",
        ),
        TextAreaField("message", label="Request Message", help_text="Message from applicant"),
        IntegerEnumField(
            "status",
            enum=ContactRequestStatus,
            label="Status",
            help_text="Current status of the request",
        ),
        StringField(
            "failure_code",
            label="Failure Code",
            help_text="Reason code when the request is pending due to inventory issues",
        ),
        JSONField(
            "failure_detail",
            label="Failure Detail",
            help_text="Structured detail for troubleshooting template shortages",
        ),
        IntegerField(
            "retry_count",
            label="Retry Count",
            help_text="Number of times this request has been retried",
        ),
        LocalDateTimeField(
            "last_retry_at",
            label="Last Retry At",
            help_text="Timestamp of the most recent retry attempt",
        ),
        LocalDateTimeField("expires_at", label="Expires At", help_text="Request expiration time"),
        LocalDateTimeField("created_at", label="Created At", help_text="Request creation time"),
        LocalDateTimeField("updated_at", label="Updated At", help_text="Last update time"),
    ]

    row_actions = ["view", "retry_request"]

    @link_row_action(
        name="retry_request",
        text="Retry",
        icon_class="fa fa-undo",
    )
    def retry_request_action(self, request: Request, pk: Any) -> str:
        """Trigger retry for hanging requests."""
        return f"/qiao-dash/contact-requests/{pk}/retry"

    async def validate(self, request: Request, data: dict[str, Any]) -> None:
        """Custom validation for contact requests."""
        from_user = data.get("_from_user")
        from_instance = data.get("_from_instance")
        to_user = data.get("_to_user")
        to_instance = data.get("_to_instance")

        # Must select exactly one from entity
        if not from_user and not from_instance:
            raise FormValidationError(
                {"_from_user": "Please select either From (User) or From (AI Instance)"}
            )
        if from_user and from_instance:
            raise FormValidationError({"_from_user": "Please select only one from entity"})

        # Must select exactly one to entity
        if not to_user and not to_instance:
            raise FormValidationError(
                {"_to_user": "Please select either To (User) or To (AI Instance)"}
            )
        if to_user and to_instance:
            raise FormValidationError({"_to_user": "Please select only one to entity"})

        # Validate status changes
        if "status" in data:
            status = data["status"]
            valid_statuses = [status.value for status in ContactRequestStatus]
            if status not in valid_statuses:
                raise FormValidationError({"status": "Invalid request status"})

        return await super().validate(request, data)

    async def before_create(self, request: Request, data: dict[str, Any], obj: Any) -> None:
        """Set auto-filled fields before database commit."""
        # Auto-fill source as ADMIN for admin panel creations
        obj.source = ContactRequestSource.ADMIN

        # Auto-infer from_type and fill from_id, from_qiao_id
        from_user = data.get("_from_user")
        from_instance = data.get("_from_instance")

        if from_user and isinstance(from_user, User):
            obj.from_type = 1  # USER
            obj.from_id = from_user.id
            obj.from_qiao_id = from_user.qiao_id
        elif from_instance and isinstance(from_instance, AIInstance):
            obj.from_type = 2  # AI
            obj.from_id = from_instance.id
            obj.from_qiao_id = from_instance.qiao_id

        # Auto-infer to_type and fill to_id, to_qiao_id
        to_user = data.get("_to_user")
        to_instance = data.get("_to_instance")

        if to_user and isinstance(to_user, User):
            obj.to_type = 1  # USER
            obj.to_id = to_user.id
            obj.to_qiao_id = to_user.qiao_id
        elif to_instance and isinstance(to_instance, AIInstance):
            obj.to_type = 2  # AI
            obj.to_id = to_instance.id
            obj.to_qiao_id = to_instance.qiao_id

        # Auto-set status to PENDING
        obj.status = ContactRequestStatus.PENDING

        # Get expiration time from config (stored in days)
        expiration_days = await get_config(request.state.session, "contact_request_expiration_days")
        obj.expires_at = datetime.now(UTC) + timedelta(days=int(expiration_days))

    async def before_edit(self, request: Request, data: dict[str, Any], obj: Any) -> None:
        """Set auto-filled fields before database commit."""
        # Auto-infer from_type and fill from_id, from_qiao_id
        from_user = data.get("_from_user")
        from_instance = data.get("_from_instance")

        if from_user and isinstance(from_user, User):
            obj.from_type = 1  # USER
            obj.from_id = from_user.id
            obj.from_qiao_id = from_user.qiao_id
        elif from_instance and isinstance(from_instance, AIInstance):
            obj.from_type = 2  # AI
            obj.from_id = from_instance.id
            obj.from_qiao_id = from_instance.qiao_id

        # Auto-infer to_type and fill to_id, to_qiao_id
        to_user = data.get("_to_user")
        to_instance = data.get("_to_instance")

        if to_user and isinstance(to_user, User):
            obj.to_type = 1  # USER
            obj.to_id = to_user.id
            obj.to_qiao_id = to_user.qiao_id
        elif to_instance and isinstance(to_instance, AIInstance):
            obj.to_type = 2  # AI
            obj.to_id = to_instance.id
            obj.to_qiao_id = to_instance.qiao_id

    def can_delete(self, request: Request) -> bool:
        """Contact requests should not be deleted for audit purposes."""
        return False


class PendingContactRequestView(CustomView):
    """Custom dashboard for hanging contact requests."""

    async def render(self, request: Request, templates):
        session = request.state.session
        stmt = (
            select(ContactRequest)
            .where(
                ContactRequest.status == ContactRequestStatus.PENDING,
                ContactRequest.failure_code.is_not(None),
            )
            .order_by(desc(ContactRequest.updated_at))
        )
        result = await session.execute(stmt)
        pending_requests = result.scalars().all()

        context = {
            "request": request,
            "items": pending_requests,
        }
        return templates.TemplateResponse("custom_views/contact_request_pending.html", context)


class ContactRequestRetryView(CustomView):
    """Internal redirect view to trigger retries via row actions."""

    add_to_menu = False

    async def render(self, request: Request, templates):
        session = request.state.session
        request_id = request.path_params.get("id")
        if not request_id:
            raise FormValidationError({"id": "Request ID missing"})

        try:
            request_id = int(request_id)
        except ValueError as exc:
            raise FormValidationError({"id": f"Invalid Request ID: {exc}"})

        await retry_pending_contact_request(session, request_id=request_id)

        referer = request.headers.get("referer") or str(request.url_for("admin:index"))
        return RedirectResponse(url=referer, status_code=303)


# Create view instances
user_view = UserView(User, name="Users", icon="fa fa-user", identity="user")
profile_view = ProfileView(Profile, name="Profiles", icon="fa fa-id-card", identity="profile")
user_profile_log_view = UserProfileLogView(
    UserProfileLog, name="Profile Logs", icon="fa fa-history", identity="user_profile_log"
)
contact_view = ContactView(Contact, name="Contacts", icon="fa fa-address-book", identity="contact")
contact_request_view = ContactRequestView(
    ContactRequest, name="Contact Requests", icon="fa fa-user-plus", identity="contact_request"
)
pending_contact_request_view = PendingContactRequestView(
    label="Pending AI Requests",
    name="contact_request_pending",
    path="/contact-requests/pending",
    icon="fa fa-hourglass-half",
)
contact_request_retry_view = ContactRequestRetryView(
    label="Retry Contact Request",
    name="contact_request_retry",
    path="/contact-requests/{id:int}/retry",
    add_to_menu=False,
)
# Export all user views
USER_MODEL_VIEWS = [
    user_view,
    profile_view,
    user_profile_log_view,
    contact_view,
    contact_request_view,
    pending_contact_request_view,
]
