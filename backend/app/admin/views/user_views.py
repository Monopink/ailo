"""User-related model views for Starlette-Admin.
Creates ModelView instances for user management and admin system models.
"""

import secrets
import string
from collections import Counter
from collections.abc import MutableMapping
from datetime import UTC, datetime, timedelta
from typing import ClassVar, cast

from sqlalchemy import desc, func, select
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from starlette.templating import Jinja2Templates
from starlette_admin import CustomView, HasOne, IntegerField, JSONField, StringField, TextAreaField
from starlette_admin.actions import link_row_action
from starlette_admin.contrib.sqla import ModelView
from starlette_admin.exceptions import FormValidationError
from starlette_admin.fields import BaseField

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
from app.models.message import MediaFile
from app.models.profile import Profile, UserProfileLog
from app.models.user import User
from app.services.contact.request_service import retry_pending_contact_request
from app.services.system_config import get_config_int
from app.type_defs import JSONDict

from .base import BaseRoleAwareModelView, InvertedBooleanField

FormData = MutableMapping[str, object | None]

PASSWORD_MIN_LENGTH = 8


class UserView(BaseRoleAwareModelView):
    """Enhanced User view with proper field configuration."""

    def can_delete(self, _request: Request) -> bool:
        return False

    exclude_fields_from_create: ClassVar[list[str]] = [
        "id",
        "qiao_id",
        "password_hash",
        "created_at",
        "updated_at",
        "last_login",
    ]
    exclude_fields_from_edit: ClassVar[list[str]] = [
        "id",
        "qiao_id",
        "password_hash",
        "created_at",
        "updated_at",
        "last_login",
    ]
    exclude_fields_from_list: ClassVar[list[str]] = ["password_hash", "password"]
    exclude_fields_from_detail: ClassVar[list[str]] = ["password_hash", "password"]

    fields_default_sort: ClassVar[list[tuple[str, bool]]] = [("created_at", True)]
    searchable_fields: ClassVar[list[str]] = ["username", "phone", "email", "qiao_id"]
    sortable_fields: ClassVar[list[str]] = [
        "id",
        "username",
        "qiao_id",
        "status",
        "user_type",
        "needs_profile_setup",
        "created_at",
        "updated_at",
        "last_login",
    ]

    fields: ClassVar[list[BaseField]] = [
        StringField("id", label="ID", help_text="Internal user ID"),
        StringField("qiao_id", label="Qiao ID", help_text="External user identifier"),
        StringField("username", label="Username", help_text="Display name for the user"),
        StringField("phone", label="Phone Number", help_text="Phone number for login"),
        StringField("email", label="Email Address", help_text="Email address for notifications"),
        StringField(
            "password",
            label="Password",
            help_text=(
                "Warning: Leave blank to keep current password unchanged. "
                f"Enter new password (min {PASSWORD_MIN_LENGTH} characters) to change."
            ),
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
        InvertedBooleanField(
            "needs_profile_setup",
            label="Profile Completed",
            help_text="Checked=Completed, Unchecked=Needed (inverted from database for clarity)",
        ),
        LocalDateTimeField("last_login", label="Last Login", help_text="Last login time"),
        LocalDateTimeField("created_at", label="Created At", help_text="Account creation time"),
        LocalDateTimeField("updated_at", label="Updated At", help_text="Last update time"),
    ]

    async def validate(self, request: Request, data: FormData) -> None:
        """Validate user data."""
        password_value = data.get("password")

        # For create operation, password is required
        if request.url.path.endswith("/create"):
            if not password_value:
                raise FormValidationError({"password": "Password is required when creating user"})

        # Validate password length if provided
        if isinstance(password_value, str) and password_value:
            if len(password_value) < PASSWORD_MIN_LENGTH:
                raise FormValidationError(
                    {"password": f"Password must be at least {PASSWORD_MIN_LENGTH} characters long"}
                )

        await super().validate(request, data)

    async def before_create(self, _request: Request, data: FormData, obj: User) -> None:
        """Hash password before creating user. Convert empty unique fields to NULL."""
        password = data.pop("password", None)

        if isinstance(password, str) and password:
            obj.password_hash = get_password_hash(password)

        # Convert empty unique fields to NULL to avoid unique constraint violation
        convert_empty_strings_to_none(obj, ["phone", "email"])

    async def before_edit(self, _request: Request, data: FormData, obj: User) -> None:
        """Hash password before updating user if password is changed.

        Convert empty unique fields to NULL.
        """
        password = data.pop("password", None)

        # Only update password if a new one is provided
        if isinstance(password, str) and password:
            obj.password_hash = get_password_hash(password)

        # Convert empty unique fields to NULL to avoid unique constraint violation
        convert_empty_strings_to_none(obj, ["phone", "email"])


class ProfileView(BaseRoleAwareModelView):
    """Enhanced Profile view with proper field configuration."""

    # Exclude auto-filled fields from create/edit
    exclude_fields_from_create: ClassVar[list[str]] = [
        "id",
        "owner_id",  # Auto-filled
        "owner_qiao_id",  # Auto-filled
        "owner_type",  # Auto-inferred from selected owner
        "avatar_key",  # Auto-filled from selected avatar_media
        "avatar_media_id",  # Auto-filled from selected avatar_media
        "created_at",
        "updated_at",
    ]
    exclude_fields_from_edit: ClassVar[list[str]] = [
        "id",
        "owner_id",  # Auto-filled
        "owner_qiao_id",  # Auto-filled
        "owner_type",  # Auto-inferred from selected owner
        "avatar_key",  # Auto-filled from selected avatar_media
        "avatar_media_id",  # Auto-filled from selected avatar_media
        "created_at",
        "updated_at",
    ]
    exclude_fields_from_list: ClassVar[list[str]] = [
        "avatar_key",
        "avatar_media_id",
    ]
    exclude_fields_from_detail: ClassVar[list[str]] = [
        "avatar_key",
        "avatar_media_id",
    ]

    def can_delete(self, _request: Request) -> bool:
        return False

    fields_default_sort: ClassVar[list[tuple[str, bool]]] = [("created_at", True)]
    searchable_fields: ClassVar[list[str]] = ["nickname", "owner_qiao_id"]
    sortable_fields: ClassVar[list[str]] = [
        "id",
        "owner_type",
        "nickname",
        "gender",
        "created_at",
        "updated_at",
    ]

    fields: ClassVar[list[BaseField]] = [
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
        HasOne(
            "avatar_media",
            identity="media_file",
            label="Avatar",
            help_text="Select avatar from media files (auto-fills avatar_key and avatar_media_id)",
            required=False,
        ),
        StringField(
            "avatar_key",
            label="Avatar Object Key",
            help_text="Object key for avatar (e.g. avatars/2025/12/xxx.webp)",
        ),
        IntegerField(
            "avatar_media_id",
            label="Avatar Media ID",
            help_text="FK to media_files.id for audit trail",
        ),
        TextAreaField(
            "avatar_prompt", label="Avatar Prompt", help_text="Description for AI-generated avatars"
        ),
        TextAreaField("bio", label="Bio", help_text="Profile biography"),
        StringField("region", label="Region", help_text="Location/region information"),
        LocalDateTimeField("created_at", label="Created At", help_text="Profile creation time"),
        LocalDateTimeField("updated_at", label="Updated At", help_text="Last update time"),
    ]

    async def validate(self, _request: Request, data: FormData) -> None:
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

    async def before_create(self, request: Request, data: FormData, obj: Profile) -> None:
        """Set auto-filled fields before database commit."""
        # Auto-fill avatar_key and avatar_media_id from selected avatar_media
        avatar_media = data.get("avatar_media")
        if avatar_media and isinstance(avatar_media, MediaFile):
            obj.avatar_key = avatar_media.object_key
            obj.avatar_media_id = avatar_media.id
        else:
            # Convert empty string to None if no media selected
            if hasattr(obj, "avatar_key") and obj.avatar_key == "":
                obj.avatar_key = None
            if hasattr(obj, "avatar_media_id") and obj.avatar_media_id == "":  # type: ignore[comparison-overlap]
                obj.avatar_media_id = None

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
                        field_name: (
                            f"Profile already exists for this owner (ID: {existing_profile.id})"
                        )
                    }
                )

    async def before_edit(self, _request: Request, data: FormData, obj: Profile) -> None:
        """Set auto-filled fields before database commit."""
        # Auto-fill avatar_key and avatar_media_id from selected avatar_media
        avatar_media = data.get("avatar_media")
        if avatar_media and isinstance(avatar_media, MediaFile):
            obj.avatar_key = avatar_media.object_key
            obj.avatar_media_id = avatar_media.id
        else:
            # Convert empty string to None if no media selected
            if hasattr(obj, "avatar_key") and obj.avatar_key == "":
                obj.avatar_key = None
            if hasattr(obj, "avatar_media_id") and obj.avatar_media_id == "":  # type: ignore[comparison-overlap]
                obj.avatar_media_id = None

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
    def can_create(self, _request: Request) -> bool:
        return False

    def can_edit(self, _request: Request) -> bool:
        return False

    def can_delete(self, _request: Request) -> bool:
        return False

    exclude_fields_from_create: ClassVar[list[str]] = [
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
    exclude_fields_from_edit: ClassVar[list[str]] = [
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

    fields_default_sort: ClassVar[list[tuple[str, bool]]] = [("created_at", True)]
    searchable_fields: ClassVar[list[str]] = ["owner_qiao_id", "field_name"]
    sortable_fields: ClassVar[list[str]] = [
        "id",
        "owner_qiao_id",
        "owner_type",
        "modified_by_type",
        "field_name",
        "created_at",
    ]

    fields: ClassVar[list[BaseField]] = [
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
        LocalDateTimeField("created_at", label="Created At", help_text="Log creation time"),
    ]


class ContactView(BaseRoleAwareModelView):
    """Enhanced Contact view with proper field configuration."""

    # Exclude auto-filled fields from create/edit
    exclude_fields_from_create: ClassVar[list[str]] = [
        "id",
        "conv_id",  # Auto-generated
        "user_id",  # Auto-filled
        "user_qiao_id",  # Auto-filled
        "contact_type",  # Auto-inferred from selected contact
        "contact_id",  # Auto-filled
        "contact_qiao_id",  # Auto-filled
        "custom_avatar_key",  # Auto-filled from selected custom_avatar_media
        "custom_avatar_media_id",  # Auto-filled from selected custom_avatar_media
        "created_at",
        "updated_at",
        "deleted_at",
    ]
    exclude_fields_from_edit: ClassVar[list[str]] = [
        "id",
        "conv_id",  # Auto-generated
        "user_id",  # Auto-filled
        "user_qiao_id",  # Auto-filled
        "contact_type",  # Auto-inferred from selected contact
        "contact_id",  # Auto-filled
        "contact_qiao_id",  # Auto-filled
        "custom_avatar_key",  # Auto-filled from selected custom_avatar_media
        "custom_avatar_media_id",  # Auto-filled from selected custom_avatar_media
        "created_at",
        "updated_at",
        "deleted_at",
    ]
    exclude_fields_from_list: ClassVar[list[str]] = [
        "custom_avatar_key",
        "custom_avatar_media_id",
    ]
    exclude_fields_from_detail: ClassVar[list[str]] = [
        "custom_avatar_key",
        "custom_avatar_media_id",
    ]

    def can_delete(self, _request: Request) -> bool:
        return False

    fields_default_sort: ClassVar[list[tuple[str, bool]]] = [("created_at", True)]
    searchable_fields: ClassVar[list[str]] = ["conv_id", "user_qiao_id", "contact_qiao_id", "alias"]
    sortable_fields: ClassVar[list[str]] = [
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

    fields: ClassVar[list[BaseField]] = [
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
        HasOne(
            "custom_avatar_media",
            identity="media_file",
            label="Custom Avatar",
            help_text="Select custom avatar from media files (auto-fills custom_avatar_key and custom_avatar_media_id)",
            required=False,
        ),
        StringField(
            "custom_avatar_key",
            label="Custom Avatar Key",
            help_text="Object key overriding contact avatar (optional)",
        ),
        IntegerField(
            "custom_avatar_media_id",
            label="Custom Avatar Media ID",
            help_text="FK to media_files.id for audit trail (optional)",
        ),
        JSONField("tags", label="Tags", help_text="Structured tag metadata (JSON)"),
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

    async def validate(self, _request: Request, data: FormData) -> None:
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

    async def before_create(self, request: Request, data: FormData, obj: Contact) -> None:
        """Set auto-filled fields before database commit."""
        # Auto-fill custom_avatar_key and custom_avatar_media_id from selected custom_avatar_media
        custom_avatar_media = data.get("custom_avatar_media")
        if custom_avatar_media and isinstance(custom_avatar_media, MediaFile):
            obj.custom_avatar_key = custom_avatar_media.object_key
            obj.custom_avatar_media_id = custom_avatar_media.id
        else:
            # Convert empty string to None if no media selected
            if hasattr(obj, "custom_avatar_key") and obj.custom_avatar_key == "":
                obj.custom_avatar_key = None
            if hasattr(obj, "custom_avatar_media_id") and obj.custom_avatar_media_id == "":  # type: ignore[comparison-overlap]
                obj.custom_avatar_media_id = None

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
        errors: dict[str, str] = {}

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

    async def before_edit(self, _request: Request, data: FormData, obj: Contact) -> None:
        """Set auto-filled fields before database commit."""
        # Auto-fill custom_avatar_key and custom_avatar_media_id from selected custom_avatar_media
        custom_avatar_media = data.get("custom_avatar_media")
        if custom_avatar_media and isinstance(custom_avatar_media, MediaFile):
            obj.custom_avatar_key = custom_avatar_media.object_key
            obj.custom_avatar_media_id = custom_avatar_media.id
        else:
            # Convert empty string to None if no media selected
            if hasattr(obj, "custom_avatar_key") and obj.custom_avatar_key == "":
                obj.custom_avatar_key = None
            if hasattr(obj, "custom_avatar_media_id") and obj.custom_avatar_media_id == "":  # type: ignore[comparison-overlap]
                obj.custom_avatar_media_id = None

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

    exclude_fields_from_create: ClassVar[list[str]] = [
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
    exclude_fields_from_edit: ClassVar[list[str]] = [
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
    exclude_fields_from_list: ClassVar[list[str]] = []

    fields_default_sort: ClassVar[list[tuple[str, bool]]] = [("created_at", True)]
    searchable_fields: ClassVar[list[str]] = ["from_qiao_id", "to_qiao_id"]
    sortable_fields: ClassVar[list[str]] = [
        "id",
        "from_qiao_id",
        "to_qiao_id",
        "source",
        "status",
        "expires_at",
        "created_at",
        "updated_at",
    ]

    fields: ClassVar[list[BaseField]] = [
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

    row_actions: ClassVar[list[str]] = ["view", "retry_request"]

    @link_row_action(
        name="retry_request",
        text="Retry",
        icon_class="fa fa-undo",
    )
    def retry_request_action(self, _request: Request, pk: int | str) -> str:
        """Trigger retry for hanging requests."""
        return f"/qiao-dash/contact-requests/{pk}/retry"

    async def validate(self, request: Request, data: FormData) -> None:
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
        status_raw = data.get("status")
        if status_raw is not None:
            valid_statuses = {status.value for status in ContactRequestStatus}
            if not isinstance(status_raw, int) or status_raw not in valid_statuses:
                raise FormValidationError({"status": "Invalid request status"})

        return await super().validate(request, data)

    async def before_create(self, request: Request, data: FormData, obj: ContactRequest) -> None:
        """Set auto-filled fields before database commit."""
        # Auto-fill source as ADMIN for admin panel creations
        obj.source = ContactRequestSource.ADMIN.value

        # Auto-infer from_type and fill from_id, from_qiao_id
        from_user = data.get("_from_user")
        from_instance = data.get("_from_instance")

        if from_user and isinstance(from_user, User):
            obj.from_type = ContactType.USER.value
            obj.from_id = from_user.id
            obj.from_qiao_id = from_user.qiao_id
        elif from_instance and isinstance(from_instance, AIInstance):
            obj.from_type = ContactType.AI.value
            obj.from_id = from_instance.id
            obj.from_qiao_id = from_instance.qiao_id

        # Auto-infer to_type and fill to_id, to_qiao_id
        to_user = data.get("_to_user")
        to_instance = data.get("_to_instance")

        if to_user and isinstance(to_user, User):
            obj.to_type = ContactType.USER.value
            obj.to_id = to_user.id
            obj.to_qiao_id = to_user.qiao_id
        elif to_instance and isinstance(to_instance, AIInstance):
            obj.to_type = ContactType.AI.value
            obj.to_id = to_instance.id
            obj.to_qiao_id = to_instance.qiao_id

        # Auto-set status to PENDING
        obj.status = ContactRequestStatus.PENDING.value

        # Get expiration time from config (stored in days)
        expiration_days = await get_config_int(
            request.state.session,
            "contact_request_expiration_days",
        )
        obj.expires_at = datetime.now(UTC) + timedelta(days=expiration_days)

    async def before_edit(self, _request: Request, data: FormData, obj: ContactRequest) -> None:
        """Set auto-filled fields before database commit."""
        # Auto-infer from_type and fill from_id, from_qiao_id
        from_user = data.get("_from_user")
        from_instance = data.get("_from_instance")

        if from_user and isinstance(from_user, User):
            obj.from_type = ContactType.USER.value
            obj.from_id = from_user.id
            obj.from_qiao_id = from_user.qiao_id
        elif from_instance and isinstance(from_instance, AIInstance):
            obj.from_type = ContactType.AI.value
            obj.from_id = from_instance.id
            obj.from_qiao_id = from_instance.qiao_id

        # Auto-infer to_type and fill to_id, to_qiao_id
        to_user = data.get("_to_user")
        to_instance = data.get("_to_instance")

        if to_user and isinstance(to_user, User):
            obj.to_type = ContactType.USER.value
            obj.to_id = to_user.id
            obj.to_qiao_id = to_user.qiao_id
        elif to_instance and isinstance(to_instance, AIInstance):
            obj.to_type = ContactType.AI.value
            obj.to_id = to_instance.id
            obj.to_qiao_id = to_instance.qiao_id

    def can_delete(self, _request: Request) -> bool:
        """Contact requests should not be deleted for audit purposes."""
        return False


class PendingContactRequestView(CustomView):
    """Custom dashboard for hanging contact requests."""

    def is_active(self, request: Request) -> bool:
        """Check if current page is pending contact requests page."""
        path = request.scope["path"]
        admin_state = getattr(request.app.state, "ADMIN", None)
        if admin_state and hasattr(admin_state, "base_url"):
            base_url = cast(str, admin_state.base_url)
            return path == f"{base_url}/pending-contact-requests"
        return "/pending-contact-requests" in path

    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
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

        items: list[JSONDict] = []
        type_counter: Counter[str] = Counter()
        for req in pending_requests:
            detail = cast(JSONDict, req.failure_detail or {})
            ai_type_id = detail.get("ai_type_id") or detail.get("type_id")
            if ai_type_id is not None:
                type_counter[str(ai_type_id)] += 1
            item: JSONDict = {
                "id": req.id,
                "from_qiao_id": req.from_qiao_id,
                "to_qiao_id": req.to_qiao_id,
                "ai_type_id": ai_type_id,
                "failure_code": req.failure_code,
                "retry_count": req.retry_count or 0,
                "last_retry_at": req.last_retry_at.isoformat() if req.last_retry_at else None,
                "updated_at": req.updated_at.isoformat() if req.updated_at else None,
                "failure_detail": detail,
            }
            items.append(item)

        top_types: list[JSONDict] = [
            {"ai_type_id": key, "count": count} for key, count in type_counter.most_common(5)
        ]

        window_start = datetime.now(UTC) - timedelta(hours=24)
        success_stmt = select(func.count(ContactRequest.id)).where(
            ContactRequest.status == ContactRequestStatus.ACCEPTED,
            ContactRequest.last_retry_at.is_not(None),
            ContactRequest.last_retry_at >= window_start,
        )
        failure_stmt = select(func.count(ContactRequest.id)).where(
            ContactRequest.status == ContactRequestStatus.PENDING,
            ContactRequest.failure_code.is_not(None),
            ContactRequest.last_retry_at.is_not(None),
            ContactRequest.last_retry_at >= window_start,
        )
        success_result = await session.execute(success_stmt)
        failure_result = await session.execute(failure_stmt)
        overview: JSONDict = {
            "pending_total": len(items),
            "type_summary": top_types,
            "last24h_success": success_result.scalar_one() or 0,
            "last24h_failed": failure_result.scalar_one() or 0,
        }

        context: dict[str, object] = {
            "request": request,
            "items": items,
            "overview": overview,
        }
        return templates.TemplateResponse("custom_views/contact_request_pending.html", context)


class ContactRequestRetryView(CustomView):
    """Internal redirect view to trigger retries via row actions."""

    add_to_menu = False

    async def render(self, request: Request, _templates: Jinja2Templates) -> Response:
        session = request.state.session
        request_id = request.path_params.get("id")
        if not request_id:
            raise FormValidationError({"id": "Request ID missing"})

        try:
            request_id = int(request_id)
        except ValueError as exc:
            raise FormValidationError({"id": f"Invalid Request ID: {exc}"}) from exc

        admin_user = request.session.get("admin_user") or {}
        operator = admin_user.get("username")
        await retry_pending_contact_request(session, request_id=request_id, operator=operator)

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
    label="Pending Requests",
    name="contact_request_pending",
    path="/pending-contact-requests",
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
