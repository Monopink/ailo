"""Entitlement-related model views for Starlette-Admin."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from enum import IntEnum, StrEnum
from typing import ClassVar

from sqlalchemy import select
from starlette.requests import Request
from starlette_admin import (
    BooleanField,
    DateTimeField,
    EnumField,
    HasOne,
    IntegerField,
    JSONField,
    StringField,
)
from starlette_admin.actions import link_row_action
from starlette_admin.exceptions import FormValidationError

from app.admin.views.base import BaseRoleAwareModelView, IntegerEnumField
from app.models.admin import AdminUser
from app.models.entitlement import (
    EntitlementReasonCode,
    EntitlementType,
    UserEntitlementAccount,
    UserEntitlementLedger,
)
from app.models.user import User


class _RecordStatus(IntEnum):
    """Generic record status for admin dictionaries."""

    ACTIVE = 1
    INACTIVE = 2


class _EntitlementMode(IntEnum):
    """Entitlement type mode."""

    CAPACITY = 1
    CONSUMABLE = 2


class _ReasonCodeAppliesTo(StrEnum):
    """Allowed admin operation scopes for one reason code."""

    GRANT = "grant"
    ADJUST = "adjust"
    BOTH = "both"


async def _get_user_qiao_id_map(request: Request) -> dict[int, str]:
    cached = getattr(request.state, "entitlement_user_qiao_id_map", None)
    if isinstance(cached, dict):
        return cached
    result = await request.state.session.execute(select(User.id, User.qiao_id))
    mapping: dict[int, str] = {}
    for user_id, qiao_id in result.all():
        key = int(user_id)
        value = str(qiao_id or "").strip()
        mapping[key] = value
    request.state.entitlement_user_qiao_id_map = mapping
    return mapping


async def _get_entitlement_type_code_map(request: Request) -> dict[int, str]:
    cached = getattr(request.state, "entitlement_type_code_map", None)
    if isinstance(cached, dict):
        return cached
    result = await request.state.session.execute(select(EntitlementType.id, EntitlementType.code))
    mapping = {int(type_id): str(code) for type_id, code in result.all()}
    request.state.entitlement_type_code_map = mapping
    return mapping


async def _get_reason_code_name_map(request: Request) -> dict[str, str]:
    cached = getattr(request.state, "entitlement_reason_name_map", None)
    if isinstance(cached, dict):
        return cached
    result = await request.state.session.execute(
        select(EntitlementReasonCode.code, EntitlementReasonCode.display_name)
    )
    mapping = {str(code): str(display_name) for code, display_name in result.all()}
    request.state.entitlement_reason_name_map = mapping
    return mapping


async def _get_admin_username_map(request: Request) -> dict[int, str]:
    cached = getattr(request.state, "entitlement_admin_username_map", None)
    if isinstance(cached, dict):
        return cached
    result = await request.state.session.execute(select(AdminUser.id, AdminUser.username))
    mapping = {int(admin_id): str(username) for admin_id, username in result.all()}
    request.state.entitlement_admin_username_map = mapping
    return mapping


class _ReadableByIntForeignKeyField(StringField):
    """Display readable text by int foreign key lookup."""

    def __init__(
        self,
        name: str,
        label: str,
        fk_attr: str,
        map_loader: Callable[[Request], Awaitable[dict[int, str]]],
    ) -> None:
        super().__init__(name=name, label=label)
        self.read_only = True
        self.searchable = False
        self.orderable = False
        self._fk_attr = fk_attr
        self._map_loader = map_loader

    async def parse_obj(self, request: Request, obj: object) -> str | None:
        raw_fk = getattr(obj, self._fk_attr, None)
        if not isinstance(raw_fk, int):
            return None
        mapping = await self._map_loader(request)
        value = mapping.get(raw_fk, "")
        if value == "":
            return None
        return value


class _ReadableByStringForeignKeyField(StringField):
    """Display readable text by string foreign key lookup."""

    def __init__(
        self,
        name: str,
        label: str,
        fk_attr: str,
        map_loader: Callable[[Request], Awaitable[dict[str, str]]],
    ) -> None:
        super().__init__(name=name, label=label)
        self.read_only = True
        self.searchable = False
        self.orderable = False
        self._fk_attr = fk_attr
        self._map_loader = map_loader

    async def parse_obj(self, request: Request, obj: object) -> str | None:
        raw_fk = getattr(obj, self._fk_attr, None)
        if not isinstance(raw_fk, str):
            return None
        key = raw_fk.strip()
        if key == "":
            return None
        mapping = await self._map_loader(request)
        value = mapping.get(key, "")
        if value == "":
            return None
        return value


class EntitlementTypeView(BaseRoleAwareModelView):
    """Read-only admin view for entitlement_types."""

    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    searchable_fields = ["id", "code", "unit"]
    sortable_fields = ["id", "code", "mode", "unit", "status"]
    fields_default_sort = [("created_at", True)]
    fields = [
        IntegerField("id", label="ID"),
        StringField("code", label="Code"),
        IntegerEnumField("mode", enum=_EntitlementMode, label="Mode"),
        StringField("unit", label="Unit"),
        IntegerEnumField("status", enum=_RecordStatus, label="Status"),
        DateTimeField("created_at", label="Created At"),
        DateTimeField("updated_at", label="Updated At"),
    ]


class EntitlementReasonCodeView(BaseRoleAwareModelView):
    """Admin view for entitlement_reason_codes."""

    exclude_fields_from_create = ["id", "is_system", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "is_system", "created_at", "updated_at"]
    searchable_fields = ["id", "code", "display_name", "description"]
    sortable_fields = ["id", "code", "display_name", "applies_to", "is_system", "status"]
    fields_default_sort = [("created_at", True)]
    fields = [
        IntegerField("id", label="ID"),
        StringField("code", label="Code"),
        StringField("display_name", label="Display Name"),
        StringField("description", label="Description", required=False),
        EnumField(
            "applies_to",
            choices=[
                (_ReasonCodeAppliesTo.GRANT.value, _ReasonCodeAppliesTo.GRANT.value),
                (_ReasonCodeAppliesTo.ADJUST.value, _ReasonCodeAppliesTo.ADJUST.value),
                (_ReasonCodeAppliesTo.BOTH.value, _ReasonCodeAppliesTo.BOTH.value),
            ],
            label="Applies To",
            required=True,
        ),
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

        applies_to_raw = data.get("applies_to")
        if applies_to_raw is None:
            raise FormValidationError({"applies_to": "Applies to is required"})
        applies_to = str(applies_to_raw).strip().lower()
        if applies_to not in {
            _ReasonCodeAppliesTo.GRANT.value,
            _ReasonCodeAppliesTo.ADJUST.value,
            _ReasonCodeAppliesTo.BOTH.value,
        }:
            raise FormValidationError({"applies_to": "Applies to must be grant, adjust or both"})
        data["applies_to"] = applies_to

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

    row_actions: ClassVar[list[str]] = ["view", "operate_entitlement"]

    @link_row_action(
        name="operate_entitlement",
        text="Operate",
        icon_class="fa fa-pen",
    )
    def operate_entitlement_row_action(self, _request: Request, pk: int | str) -> str:
        """Jump to entitlement operation console with account preset."""
        return f"/qiao-dash/entitlement-operations?preset_account_id={pk}"

    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    searchable_fields = ["id", "user_id", "entitlement_type_id"]
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
        _ReadableByIntForeignKeyField(
            "user_qiao_id",
            label="User Qiao ID",
            fk_attr="user_id",
            map_loader=_get_user_qiao_id_map,
        ),
        HasOne(
            "entitlement_type",
            identity="entitlement_types",
            label="Entitlement Type",
            required=True,
        ),
        _ReadableByIntForeignKeyField(
            "entitlement_type_code",
            label="Entitlement Type Code",
            fk_attr="entitlement_type_id",
            map_loader=_get_entitlement_type_code_map,
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
        "id",
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
        _ReadableByIntForeignKeyField(
            "user_qiao_id",
            label="User Qiao ID",
            fk_attr="user_id",
            map_loader=_get_user_qiao_id_map,
        ),
        HasOne(
            "entitlement_type",
            identity="entitlement_types",
            label="Entitlement Type",
            required=True,
        ),
        _ReadableByIntForeignKeyField(
            "entitlement_type_code",
            label="Entitlement Type Code",
            fk_attr="entitlement_type_id",
            map_loader=_get_entitlement_type_code_map,
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
        _ReadableByStringForeignKeyField(
            "reason_code_name",
            label="Reason Code Name",
            fk_attr="reason_code",
            map_loader=_get_reason_code_name_map,
        ),
        HasOne(
            "operator_admin_user",
            identity="admin_user",
            label="Operator Admin User",
            required=False,
        ),
        _ReadableByIntForeignKeyField(
            "operator_admin_username",
            label="Operator Admin Username",
            fk_attr="operator_admin_user_id",
            map_loader=_get_admin_username_map,
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
