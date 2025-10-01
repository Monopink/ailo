"""
Business process related admin views.

This module contains Starlette-Admin views for managing business processes
like contact requests and other workflow-related functionality.
"""

from typing import Dict, Any
from starlette.requests import Request
from starlette_admin.contrib.sqla import ModelView
from starlette_admin import EnumField, StringField, IntegerField, DateTimeField, TextAreaField
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

    exclude_fields_from_create = ["id", "from_id", "to_id", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "from_id", "to_id", "created_at", "updated_at"]
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
        StringField("from_qiao_id", label="From Qiao ID", help_text="Applicant external identifier"),
        EnumField(
            "from_type",
            choices=[(1, "User"), (2, "AI"), (3, "Official")],
            label="From Type",
            help_text="Type of applicant",
        ),
        StringField("from_id", label="From ID", help_text="Applicant snowflake ID"),
        StringField("to_qiao_id", label="To Qiao ID", help_text="Target external identifier"),
        EnumField(
            "to_type",
            choices=[(1, "User"), (2, "AI"), (3, "Official")],
            label="To Type",
            help_text="Type of target",
        ),
        StringField("to_id", label="To ID", help_text="Target snowflake ID"),
        EnumField(
            "source",
            enum=ContactRequestSource,
            label="Request Source",
            help_text="How the contact request was initiated",
        ),
        TextAreaField("message", label="Request Message", help_text="Message from applicant"),
        EnumField(
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
        # Validate status changes
        if "status" in data:
            status = data["status"]
            valid_statuses = [status.value for status in ContactRequestStatus]
            if status not in valid_statuses:
                raise FormValidationError({"status": "Invalid request status"})

        # Additional validation can be added here if needed

        return await super().validate(request, data)

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
        EnumField(
            "from_type",
            enum=MessageParticipantType,
            label="Sender Type",
            help_text="Type of message sender",
        ),
        StringField("from_id", label="Sender ID", help_text="Sender snowflake ID"),
        StringField("from_qiao_id", label="Sender Qiao ID", help_text="Sender external identifier"),
        EnumField(
            "to_type",
            enum=MessageParticipantType,
            label="Receiver Type",
            help_text="Type of message receiver",
        ),
        StringField("to_id", label="Receiver ID", help_text="Receiver snowflake ID"),
        StringField("to_qiao_id", label="Receiver Qiao ID", help_text="Receiver external identifier"),
        EnumField(
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
