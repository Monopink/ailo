"""Entitlement-related model views for Starlette-Admin."""

from __future__ import annotations

import re
from enum import IntEnum

from starlette.requests import Request
from starlette_admin import (
    BooleanField,
    DateTimeField,
    HasOne,
    IntegerField,
    JSONField,
    StringField,
)
from starlette_admin.exceptions import FormValidationError

from app.admin.views.base import BaseRoleAwareModelView, IntegerEnumField
from app.models.entitlement import (
    EntitlementReasonCode,
    EntitlementType,
    UserEntitlementAccount,
    UserEntitlementLedger,
)


class _RecordStatus(IntEnum):
    """Generic record status for admin dictionaries."""

    ACTIVE = 1
    INACTIVE = 2


class EntitlementTypeView(BaseRoleAwareModelView):
    """Read-only admin view for entitlement_types."""

    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    searchable_fields = ["code", "unit"]
    sortable_fields = ["id", "code", "mode", "unit", "status"]
    fields_default_sort = [("created_at", True)]
    fields = [
        IntegerField("id", label="ID"),
        StringField("code", label="Code"),
        IntegerField("mode", label="Mode"),
        StringField("unit", label="Unit"),
        IntegerField("status", label="Status"),
        DateTimeField("created_at", label="Created At"),
        DateTimeField("updated_at", label="Updated At"),
    ]


class EntitlementReasonCodeView(BaseRoleAwareModelView):
    """Admin view for entitlement_reason_codes."""

    exclude_fields_from_create = ["id", "is_system", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "is_system", "created_at", "updated_at"]
    searchable_fields = ["code", "display_name", "description"]
    sortable_fields = ["id", "code", "display_name", "is_system", "status"]
    fields_default_sort = [("created_at", True)]
    fields = [
        IntegerField("id", label="ID"),
        StringField("code", label="Code"),
        StringField("display_name", label="Display Name"),
        StringField("description", label="Description", required=False),
        BooleanField("is_system", label="Is System"),
        IntegerEnumField("status", enum=_RecordStatus, label="Status"),
        DateTimeField("created_at", label="Created At"),
        DateTimeField("updated_at", label="Updated At"),
    ]

    async def before_create(
        self, request: Request, data: dict[str, object], obj: EntitlementReasonCode
    ) -> None:
        obj.is_system = False
        await super().before_create(request, data, obj)

    async def validate(self, request: Request, data: dict[str, object]) -> None:
        code_raw = data.get("code")
        if code_raw is not None:
            code = str(code_raw).strip().lower()
            if not re.fullmatch(r"^[a-z][a-z0-9_]{1,63}$", code):
                raise FormValidationError({"code": "Code must match ^[a-z][a-z0-9_]{1,63}$"})
            data["code"] = code

        display_name_raw = data.get("display_name")
        if display_name_raw is not None:
            display_name = str(display_name_raw).strip()
            if display_name == "":
                raise FormValidationError({"display_name": "Display name is required"})
            data["display_name"] = display_name

        description_raw = data.get("description")
        if description_raw is not None:
            description = str(description_raw).strip()
            data["description"] = description if description != "" else None

        await super().validate(request, data)

    async def before_edit(
        self, request: Request, data: dict[str, object], obj: EntitlementReasonCode
    ) -> None:
        if bool(obj.is_system):
            raise FormValidationError(
                {"code": "System reason code is read-only and cannot be edited"}
            )
        await super().before_edit(request, data, obj)

    def can_delete(self, request: Request) -> bool:
        return False


class UserEntitlementAccountView(BaseRoleAwareModelView):
    """Read-only admin view for user_entitlement_accounts."""

    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    searchable_fields = ["user_id", "entitlement_type_id"]
    sortable_fields = [
        "id",
        "user_id",
        "entitlement_type_id",
        "granted_total",
        "used_total",
        "available_total",
        "version",
    ]
    fields_default_sort = [("created_at", True)]
    fields = [
        IntegerField("id", label="ID"),
        HasOne("user", identity="user", label="User", required=True),
        HasOne(
            "entitlement_type",
            identity="entitlement_types",
            label="Entitlement Type",
            required=True,
        ),
        IntegerField("granted_total", label="Granted Total"),
        IntegerField("used_total", label="Used Total"),
        IntegerField("available_total", label="Available Total"),
        IntegerField("version", label="Version"),
        DateTimeField("created_at", label="Created At"),
        DateTimeField("updated_at", label="Updated At"),
    ]


class UserEntitlementLedgerView(BaseRoleAwareModelView):
    """Read-only admin view for user_entitlement_ledger."""

    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    searchable_fields = [
        "user_id",
        "entitlement_type_id",
        "source_type",
        "reason_code",
        "operator_admin_user_id",
        "idempotency_key",
    ]
    sortable_fields = [
        "id",
        "user_id",
        "entitlement_type_id",
        "action_type",
        "delta_granted",
        "delta_used",
        "source_type",
        "source_id",
        "reason_code",
        "operator_admin_user_id",
        "idempotency_key",
        "effective_at",
        "created_at",
    ]
    fields_default_sort = [("created_at", True)]
    fields = [
        IntegerField("id", label="ID"),
        HasOne("user", identity="user", label="User", required=True),
        HasOne(
            "entitlement_type",
            identity="entitlement_types",
            label="Entitlement Type",
            required=True,
        ),
        IntegerField("action_type", label="Action Type"),
        IntegerField("delta_granted", label="Delta Granted"),
        IntegerField("delta_used", label="Delta Used"),
        StringField("source_type", label="Source Type"),
        IntegerField("source_id", label="Source ID"),
        HasOne(
            "reason_code_ref",
            identity="entitlement_reason_codes",
            label="Reason Code",
            required=False,
        ),
        HasOne(
            "operator_admin_user",
            identity="admin_user",
            label="Operator Admin User",
            required=False,
        ),
        StringField("idempotency_key", label="Idempotency Key"),
        DateTimeField("effective_at", label="Effective At"),
        JSONField("event_payload", label="Event Payload", required=False),
        DateTimeField("created_at", label="Created At"),
    ]


entitlement_type_view = EntitlementTypeView(
    EntitlementType, name="Entitlement Types", icon="fa fa-tags", identity="entitlement_types"
)
entitlement_reason_code_view = EntitlementReasonCodeView(
    EntitlementReasonCode,
    name="Entitlement Reason Codes",
    icon="fa fa-book",
    identity="entitlement_reason_codes",
)
user_entitlement_account_view = UserEntitlementAccountView(
    UserEntitlementAccount,
    name="User Entitlement Accounts",
    icon="fa fa-gift",
    identity="user_entitlement_accounts",
)
user_entitlement_ledger_view = UserEntitlementLedgerView(
    UserEntitlementLedger,
    name="User Entitlement Ledger",
    icon="fa fa-list-alt",
    identity="user_entitlement_ledger",
)

ENTITLEMENT_MODEL_VIEWS = [
    entitlement_type_view,
    entitlement_reason_code_view,
    user_entitlement_account_view,
    user_entitlement_ledger_view,
]
