"""
Business process related admin views.

This module contains Starlette-Admin views for managing business processes
like contact requests and other workflow-related functionality.
"""

from typing import Dict, Any
from starlette.requests import Request
from starlette_admin.contrib.sqla import ModelView
from starlette_admin import StringField, IntegerField, DateTimeField, TextAreaField, HasOne
from admin.views.base import IntegerEnumField
from starlette_admin.exceptions import FormValidationError

# Import business models
from models.contact import ContactRequest
from models.message import MessageDeliveryFailure

# Import enums
from enums import ContactRequestSource, ContactRequestStatus, MessageParticipantType, MessageType


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
    exclude_fields_from_list = ["message"]

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
            "_from_character",
            identity="ai_character",
            label="From (AI Character)",
            help_text="Select an AI character as applicant",
            required=False,
        ),
        StringField("from_qiao_id", label="From Qiao ID", help_text="Applicant external identifier"),
        # Polymorphic to fields - select one, to_type is auto-inferred
        HasOne(
            "_to_user",
            identity="user",
            label="To (User)",
            help_text="Select a user as target",
            required=False,
        ),
        HasOne(
            "_to_character",
            identity="ai_character",
            label="To (AI Character)",
            help_text="Select an AI character as target",
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
        DateTimeField("expires_at", label="Expires At", help_text="Request expiration time"),
        DateTimeField("created_at", label="Created At", help_text="Request creation time"),
        DateTimeField("updated_at", label="Updated At", help_text="Last update time"),
    ]

    async def validate(self, request: Request, data: Dict[str, Any]) -> None:
        """Custom validation for contact requests."""
        from_user = data.get("_from_user")
        from_character = data.get("_from_character")
        to_user = data.get("_to_user")
        to_character = data.get("_to_character")

        # Must select exactly one from entity
        if not from_user and not from_character:
            raise FormValidationError(
                {"_from_user": "Please select either From (User) or From (AI Character)"}
            )
        if from_user and from_character:
            raise FormValidationError({"_from_user": "Please select only one from entity"})

        # Must select exactly one to entity
        if not to_user and not to_character:
            raise FormValidationError({"_to_user": "Please select either To (User) or To (AI Character)"})
        if to_user and to_character:
            raise FormValidationError({"_to_user": "Please select only one to entity"})

        # Validate status changes
        if "status" in data:
            status = data["status"]
            valid_statuses = [status.value for status in ContactRequestStatus]
            if status not in valid_statuses:
                raise FormValidationError({"status": "Invalid request status"})

        return await super().validate(request, data)

    async def before_create(self, request: Request, data: Dict[str, Any], obj: Any) -> None:
        """Set auto-filled fields before database commit."""
        from models.user import User
        from models.ai.character import AICharacter

        # Auto-fill source as ADMIN for admin panel creations
        obj.source = ContactRequestSource.ADMIN

        # Auto-infer from_type and fill from_id, from_qiao_id
        from_user = data.get("_from_user")
        from_character = data.get("_from_character")

        if from_user and isinstance(from_user, User):
            obj.from_type = 1  # USER
            obj.from_id = from_user.id
            obj.from_qiao_id = from_user.qiao_id
        elif from_character and isinstance(from_character, AICharacter):
            obj.from_type = 2  # AI
            obj.from_id = from_character.id
            obj.from_qiao_id = from_character.qiao_id

        # Auto-infer to_type and fill to_id, to_qiao_id
        to_user = data.get("_to_user")
        to_character = data.get("_to_character")

        if to_user and isinstance(to_user, User):
            obj.to_type = 1  # USER
            obj.to_id = to_user.id
            obj.to_qiao_id = to_user.qiao_id
        elif to_character and isinstance(to_character, AICharacter):
            obj.to_type = 2  # AI
            obj.to_id = to_character.id
            obj.to_qiao_id = to_character.qiao_id

        # Auto-set status to PENDING
        obj.status = ContactRequestStatus.PENDING

        # Auto-calculate expires_at from system config
        from datetime import datetime, timedelta
        from services.system_config import get_config

        # Get expiration time from config (default: 259200 seconds = 72 hours = 3 days)
        expiration_seconds = await get_config(request.state.session, "contact_request_expiration", 259200)
        obj.expires_at = datetime.utcnow() + timedelta(seconds=int(expiration_seconds))

    async def before_edit(self, request: Request, data: Dict[str, Any], obj: Any) -> None:
        """Set auto-filled fields before database commit."""
        from models.user import User
        from models.ai.character import AICharacter

        # Auto-infer from_type and fill from_id, from_qiao_id
        from_user = data.get("_from_user")
        from_character = data.get("_from_character")

        if from_user and isinstance(from_user, User):
            obj.from_type = 1  # USER
            obj.from_id = from_user.id
            obj.from_qiao_id = from_user.qiao_id
        elif from_character and isinstance(from_character, AICharacter):
            obj.from_type = 2  # AI
            obj.from_id = from_character.id
            obj.from_qiao_id = from_character.qiao_id

        # Auto-infer to_type and fill to_id, to_qiao_id
        to_user = data.get("_to_user")
        to_character = data.get("_to_character")

        if to_user and isinstance(to_user, User):
            obj.to_type = 1  # USER
            obj.to_id = to_user.id
            obj.to_qiao_id = to_user.qiao_id
        elif to_character and isinstance(to_character, AICharacter):
            obj.to_type = 2  # AI
            obj.to_id = to_character.id
            obj.to_qiao_id = to_character.qiao_id

    def can_delete(self, request: Request) -> bool:
        """Contact requests should not be deleted for audit purposes."""
        return False


class MessageDeliveryFailureView(ModelView):
    """Enhanced Message Delivery Failure view for failed message management."""

    label = "Message Failures"
    name = "Message Failures"

    exclude_fields_from_create = ["id", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "msg_id_server", "from_id", "to_id", "created_at", "updated_at"]
    exclude_fields_from_list = ["content", "fail_detail"]

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["msg_id_server", "from_qiao_id", "to_qiao_id", "fail_reason_code"]
    sortable_fields = [
        "id",
        "msg_id_server",
        "from_qiao_id",
        "to_qiao_id",
        "message_type",
        "retry_count",
        "max_retry_count",
        "next_retry_at",
        "created_at",
    ]

    fields = [
        StringField("msg_id_server", label="Message ID", help_text="Original message ID"),
        IntegerEnumField(
            "from_type",
            enum=MessageParticipantType,
            label="Sender Type",
            help_text="Type of message sender",
        ),
        StringField("from_id", label="Sender ID", help_text="Sender snowflake ID"),
        StringField("from_qiao_id", label="Sender Qiao ID", help_text="Sender external identifier"),
        IntegerEnumField(
            "to_type",
            enum=MessageParticipantType,
            label="Receiver Type",
            help_text="Type of message receiver",
        ),
        StringField("to_id", label="Receiver ID", help_text="Receiver snowflake ID"),
        StringField("to_qiao_id", label="Receiver Qiao ID", help_text="Receiver external identifier"),
        IntegerEnumField(
            "message_type",
            enum=MessageType,
            label="Message Type",
            help_text="Type of failed message",
        ),
        TextAreaField("content", label="Message Content", help_text="Original message content"),
        StringField("fail_reason_code", label="Failure Code", help_text="Error reason code"),
        TextAreaField("fail_detail", label="Failure Details", help_text="Detailed error information"),
        IntegerField("retry_count", label="Retry Count", help_text="Current retry attempts"),
        IntegerField("max_retry_count", label="Max Retries", help_text="Maximum retry attempts allowed"),
        DateTimeField("next_retry_at", label="Next Retry", help_text="Scheduled next retry time"),
        DateTimeField("created_at", label="Created At", help_text="Failure record creation time"),
        DateTimeField("updated_at", label="Updated At", help_text="Last update time"),
    ]

    async def validate(self, request: Request, data: Dict[str, Any]) -> None:
        """Custom validation for message delivery failures."""
        # Validate retry count
        if "retry_count" in data and "max_retry_count" in data:
            if data["retry_count"] > data["max_retry_count"]:
                raise FormValidationError({"retry_count": "Retry count cannot exceed maximum retries"})

        # Validate message type
        if "message_type" in data:
            message_type = data["message_type"]
            valid_types = [msg_type.value for msg_type in MessageType]
            if message_type not in valid_types:
                raise FormValidationError({"message_type": "Invalid message type"})

        return await super().validate(request, data)

    def can_delete(self, request: Request) -> bool:
        """Allow deletion of failure records after successful retry or manual resolution."""
        return True


# Create view instances
contact_request_view = ContactRequestView(
    ContactRequest, name="Contact Requests", icon="fa fa-user-plus", identity="contact_request"
)

message_delivery_failure_view = MessageDeliveryFailureView(
    MessageDeliveryFailure,
    name="Message Failures",
    icon="fa fa-exclamation-circle",
    identity="message_delivery_failure",
)

# Export business views
BUSINESS_MODEL_VIEWS = [
    contact_request_view,
    message_delivery_failure_view,
]
