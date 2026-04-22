"""Growth-related model views for Starlette-Admin."""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import datetime
from typing import Any, cast

from sqlalchemy import func, select
from starlette.requests import Request
from starlette_admin import DateTimeField, HasOne, IntegerField, JSONField, StringField
from starlette_admin.exceptions import FormValidationError

from app.admin.views.base import BaseRoleAwareModelView, IntegerEnumField
from app.enums.campaign import CampaignStatus
from app.enums.growth import (
    GrowthRewardRuleStatus,
    GrowthRewardScopeType,
    GrowthRewardTargetRole,
    GrowthRewardTriggerEvent,
)
from app.enums.invite import (
    InviteCodeStatus,
    InviteEventType,
    InviteShareTemplateStatus,
)
from app.enums.redeem import RedeemCodeBatchStatus, RedeemCodeMode, RedeemCodeStatus
from app.models.campaign import Campaign, CampaignAttribution
from app.models.growth_reward import GrowthRewardApply, GrowthRewardRule
from app.models.invite import (
    InviteBinding,
    InviteCode,
    InviteEvent,
    InviteRecognitionLog,
    InviteShareTemplate,
)
from app.models.redeem import RedeemCode, RedeemCodeBatch, RedeemCodeClaim

INVITE_CODE_LENGTH = 6
REDEEM_CODE_MIN_LENGTH = 4
REDEEM_CODE_MAX_LENGTH = 32
LOCALE_PATTERN = re.compile(r"^[a-z]{2}(?:-[A-Z]{2})?$")


def _extract_relation_id(value: object) -> int | None:
    """Extract a relation primary key from a HasOne field value."""
    relation_id = getattr(value, "id", value)
    if relation_id is None:
        return None
    try:
        return int(cast(Any, relation_id))
    except (TypeError, ValueError):
        return None


class _InviteEventCountField(StringField):
    """Computed field to show event count by code id."""

    def __init__(self, name: str, label: str, event_type: InviteEventType) -> None:
        super().__init__(name=name, label=label)
        self._event_type = event_type
        self.read_only = True
        self.searchable = False
        self.orderable = False

    async def parse_obj(self, request: Request, obj: Any) -> str:
        try:
            code_id = getattr(obj, "id", None)
            if not isinstance(code_id, int):
                return "0"
            count_map = getattr(request.state, "invite_event_count_map", None)
            if isinstance(count_map, dict):
                return str(int(count_map.get((code_id, int(self._event_type)), 0)))
            session = request.state.session
            result = await session.execute(
                select(func.count(InviteEvent.id)).where(
                    InviteEvent.invite_code_id == code_id,
                    InviteEvent.event_type == int(self._event_type),
                )
            )
            value = result.scalar_one()
            return str(int(value))
        except Exception:
            return "0"


class InviteCodeView(BaseRoleAwareModelView):
    """Admin view for invite_codes."""

    exclude_fields_from_create = ["id", "owner_user_id", "created_at", "updated_at"]
    exclude_fields_from_edit = [
        "id",
        "code",
        "owner_user",
        "owner_user_id",
        "created_at",
        "updated_at",
    ]
    searchable_fields = ["code", "owner_user_id"]
    sortable_fields = ["id", "code", "owner_user_id", "status", "created_at", "updated_at"]
    fields_default_sort = [("created_at", True)]

    fields = [
        IntegerField("id", label="ID"),
        StringField("code", label="Invite Code", required=True),
        HasOne("owner_user", identity="user", label="Owner User", required=True),
        IntegerEnumField("status", enum=InviteCodeStatus, label="Status", required=True),
        _InviteEventCountField("open_count", "Open Count", InviteEventType.OPEN),
        _InviteEventCountField(
            "bind_success_count", "Bind Success Count", InviteEventType.BIND_SUCCESS
        ),
        DateTimeField("created_at", label="Created At"),
        DateTimeField("updated_at", label="Updated At"),
    ]

    async def find_all(
        self,
        request: Request,
        skip: int = 0,
        limit: int = 100,
        where: dict[str, Any] | str | None = None,
        order_by: list[str] | None = None,
    ) -> Sequence[Any]:
        rows = await super().find_all(
            request=request,
            skip=skip,
            limit=limit,
            where=where,
            order_by=order_by,
        )
        code_ids = [row_id for row in rows if isinstance((row_id := getattr(row, "id", None)), int)]
        count_map: dict[tuple[int, int], int] = {}
        if code_ids:
            session = request.state.session
            result = await session.execute(
                select(
                    InviteEvent.invite_code_id,
                    InviteEvent.event_type,
                    func.count(InviteEvent.id),
                )
                .where(
                    InviteEvent.invite_code_id.in_(code_ids),
                    InviteEvent.event_type.in_(
                        [int(InviteEventType.OPEN), int(InviteEventType.BIND_SUCCESS)]
                    ),
                )
                .group_by(InviteEvent.invite_code_id, InviteEvent.event_type)
            )
            for invite_code_id, event_type, count in result.all():
                if isinstance(invite_code_id, int):
                    count_map[(invite_code_id, int(event_type))] = int(count)
        request.state.invite_event_count_map = count_map
        return rows

    async def validate(self, request: Request, data: dict[str, Any]) -> None:
        if "code" in data:
            code = str(data.get("code", "")).strip().upper()
            if len(code) != INVITE_CODE_LENGTH or not code.isascii() or not code.isalnum():
                raise FormValidationError(
                    {"code": "Invite code must be 6 uppercase letters/digits"}
                )
            data["code"] = code

        if "owner_user" in data or "owner_user_id" in data:
            owner_user_id = _extract_relation_id(data.get("owner_user"))
            if owner_user_id is None:
                raise FormValidationError({"owner_user": "Owner user is required"})
            data["owner_user_id"] = owner_user_id

        try:
            status_value = int(data.get("status"))
        except Exception as exc:
            raise FormValidationError({"status": "Status must be an integer"}) from exc
        if status_value not in (int(InviteCodeStatus.ACTIVE), int(InviteCodeStatus.INACTIVE)):
            raise FormValidationError({"status": "Invalid status"})
        data["status"] = status_value

        await super().validate(request, data)

    async def before_create(self, request: Request, data: dict[str, Any], obj: InviteCode) -> None:
        owner_user_id = _extract_relation_id(data.get("owner_user"))
        if owner_user_id is not None:
            obj.owner_user_id = owner_user_id
        await super().before_create(request, data, obj)

    async def before_edit(self, request: Request, data: dict[str, Any], obj: InviteCode) -> None:
        owner_user_id = _extract_relation_id(data.get("owner_user"))
        if owner_user_id is not None:
            obj.owner_user_id = owner_user_id
        await super().before_edit(request, data, obj)

    def can_delete(self, request: Request) -> bool:
        return False

    def can_create(self, request: Request) -> bool:
        return False


class InviteBindingView(BaseRoleAwareModelView):
    """Read-only admin view for invite_bindings."""

    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    searchable_fields = ["invitee_user_id", "inviter_user_id_snapshot", "code_snapshot"]
    sortable_fields = [
        "id",
        "invitee_user_id",
        "invite_code_id",
        "inviter_user_id_snapshot",
        "created_at",
        "updated_at",
    ]
    fields_default_sort = [("created_at", True)]
    fields = [
        IntegerField("id", label="ID"),
        HasOne("invitee_user", identity="user", label="Invitee User", required=True),
        HasOne("invite_code", identity="invite_codes", label="Invite Code", required=True),
        StringField("code_snapshot", label="Code Snapshot"),
        HasOne("inviter_user", identity="user", label="Inviter User", required=True),
        DateTimeField("created_at", label="Created At"),
        DateTimeField("updated_at", label="Updated At"),
    ]


class InviteEventView(BaseRoleAwareModelView):
    """Read-only admin view for invite_events."""

    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    searchable_fields = ["actor_user_id", "invite_code_id", "event_source", "code_snapshot"]
    sortable_fields = [
        "id",
        "event_type",
        "actor_user_id",
        "invite_code_id",
        "event_source",
        "created_at",
    ]
    fields_default_sort = [("created_at", True)]
    fields = [
        IntegerField("id", label="ID"),
        IntegerEnumField("event_type", enum=InviteEventType, label="Event Type"),
        HasOne("actor_user", identity="user", label="Actor User", required=False),
        HasOne("invite_code", identity="invite_codes", label="Invite Code", required=False),
        StringField("event_source", label="Event Source"),
        StringField("code_snapshot", label="Code Snapshot", required=False),
        JSONField("event_payload", label="Event Payload", required=False),
        DateTimeField("created_at", label="Created At"),
    ]


class InviteRecognitionLogView(BaseRoleAwareModelView):
    """Read-only admin view for invite_recognition_logs."""

    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    searchable_fields = ["source", "trigger", "first_candidate", "recognized_code", "raw_text"]
    sortable_fields = ["id", "source", "trigger", "valid", "created_at"]
    fields_default_sort = [("created_at", True)]
    fields = [
        IntegerField("id", label="ID"),
        HasOne("actor_user", identity="user", label="Actor User", required=False),
        HasOne("invite_code", identity="invite_codes", label="Invite Code", required=False),
        StringField("source", label="Source"),
        StringField("trigger", label="Trigger"),
        StringField("first_candidate", label="First Candidate", required=False),
        StringField("recognized_code", label="Recognized Code", required=False),
        StringField("valid", label="Valid"),
        StringField("bindable", label="Bindable", required=False),
        StringField("raw_text", label="Raw Text"),
        DateTimeField("created_at", label="Created At"),
    ]


class InviteShareTemplateView(BaseRoleAwareModelView):
    """Admin view for invite_share_templates."""

    searchable_fields = ["template_text", "locale"]
    sortable_fields = ["id", "status", "priority", "locale", "created_at", "updated_at"]
    fields_default_sort = [("priority", False), ("id", False)]
    fields = [
        IntegerField("id", label="ID"),
        StringField("template_text", label="Template Text", required=True),
        IntegerEnumField(
            "status",
            enum=InviteShareTemplateStatus,
            label="Status",
            required=True,
        ),
        IntegerField("priority", label="Priority", required=True),
        StringField("locale", label="Locale", required=True),
        DateTimeField("created_at", label="Created At"),
        DateTimeField("updated_at", label="Updated At"),
    ]
    exclude_fields_from_create = ["id", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "created_at", "updated_at"]

    async def validate(self, request: Request, data: dict[str, Any]) -> None:
        template_text = str(data.get("template_text", "")).strip()
        if template_text == "":
            raise FormValidationError({"template_text": "Template text is required"})
        data["template_text"] = template_text

        try:
            status_value = int(data.get("status"))
        except Exception as exc:
            raise FormValidationError({"status": "Status must be an integer"}) from exc
        if status_value not in (
            int(InviteShareTemplateStatus.ACTIVE),
            int(InviteShareTemplateStatus.INACTIVE),
        ):
            raise FormValidationError({"status": "Invalid status"})
        data["status"] = status_value

        try:
            priority_value = int(data.get("priority"))
        except Exception as exc:
            raise FormValidationError({"priority": "Priority must be an integer"}) from exc
        data["priority"] = priority_value

        locale = str(data.get("locale", "")).strip()
        if LOCALE_PATTERN.fullmatch(locale) is None:
            raise FormValidationError({"locale": "Locale must be like zh-CN or en"})
        data["locale"] = locale

        await super().validate(request, data)

    def can_delete(self, request: Request) -> bool:
        return False


def _parse_datetime_field(name: str, value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        text = value.strip()
        if text == "":
            return None
        try:
            return datetime.fromisoformat(text)
        except ValueError as exc:
            raise FormValidationError({name: "Invalid datetime format"}) from exc
    raise FormValidationError({name: "Invalid datetime format"})


class CampaignView(BaseRoleAwareModelView):
    """Admin view for campaigns."""

    exclude_fields_from_create = ["id", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "created_at", "updated_at"]
    searchable_fields = ["code", "name"]
    sortable_fields = [
        "id",
        "code",
        "name",
        "status",
        "starts_at",
        "ends_at",
        "created_at",
        "updated_at",
    ]
    fields_default_sort = [("created_at", True)]
    fields = [
        IntegerField("id", label="ID"),
        StringField("code", label="Campaign Code", required=True),
        StringField("name", label="Campaign Name", required=True),
        StringField("description", label="Description", required=False),
        IntegerEnumField("status", enum=CampaignStatus, label="Status", required=True),
        DateTimeField("starts_at", label="Starts At", required=False),
        DateTimeField("ends_at", label="Ends At", required=False),
        DateTimeField("created_at", label="Created At"),
        DateTimeField("updated_at", label="Updated At"),
    ]

    async def validate(self, request: Request, data: dict[str, Any]) -> None:
        code = str(data.get("code", "")).strip().upper()
        if code == "":
            raise FormValidationError({"code": "Campaign code is required"})
        data["code"] = code
        name = str(data.get("name", "")).strip()
        if name == "":
            raise FormValidationError({"name": "Campaign name is required"})
        data["name"] = name
        data["starts_at"] = _parse_datetime_field("starts_at", data.get("starts_at"))
        data["ends_at"] = _parse_datetime_field("ends_at", data.get("ends_at"))
        if (
            data["starts_at"] is not None
            and data["ends_at"] is not None
            and data["ends_at"] <= data["starts_at"]
        ):
            raise FormValidationError({"ends_at": "Ends at must be later than starts at"})
        await super().validate(request, data)

    def can_delete(self, request: Request) -> bool:
        return False


class CampaignAttributionView(BaseRoleAwareModelView):
    """Read-only admin view for campaign_attributions."""

    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    searchable_fields = ["user_id", "campaign_id", "attribution_source"]
    sortable_fields = ["id", "user_id", "campaign_id", "attributed_at", "created_at", "updated_at"]
    fields_default_sort = [("created_at", True)]
    fields = [
        IntegerField("id", label="ID"),
        HasOne("user", identity="user", label="User", required=True),
        HasOne("campaign", identity="campaigns", label="Campaign", required=True),
        StringField("attribution_source", label="Source"),
        DateTimeField("attributed_at", label="Attributed At"),
        JSONField("event_payload", label="Event Payload", required=False),
        DateTimeField("created_at", label="Created At"),
        DateTimeField("updated_at", label="Updated At"),
    ]


class GrowthRewardRuleView(BaseRoleAwareModelView):
    """Admin view for growth_reward_rules."""

    exclude_fields_from_create = [
        "id",
        "scope_id",
        "entitlement_type_id",
        "created_at",
        "updated_at",
    ]
    exclude_fields_from_edit = ["id", "scope_id", "entitlement_type_id", "created_at", "updated_at"]
    searchable_fields = ["scope_type", "scope_id", "entitlement_type_id"]
    sortable_fields = [
        "id",
        "trigger_event",
        "target_role",
        "scope_type",
        "scope_id",
        "entitlement_type_id",
        "delta_granted",
        "max_rewards_per_actor",
        "priority",
        "status",
        "created_at",
        "updated_at",
    ]
    fields_default_sort = [("priority", False), ("id", False)]
    fields = [
        IntegerField("id", label="ID"),
        IntegerEnumField(
            "trigger_event", enum=GrowthRewardTriggerEvent, label="Trigger Event", required=True
        ),
        IntegerEnumField(
            "target_role", enum=GrowthRewardTargetRole, label="Target Role", required=True
        ),
        IntegerEnumField(
            "scope_type", enum=GrowthRewardScopeType, label="Scope Type", required=True
        ),
        HasOne("campaign", identity="campaigns", label="Campaign Scope", required=False),
        HasOne(
            "redeem_batch",
            identity="redeem_code_batches",
            label="Redeem Batch Scope",
            required=False,
        ),
        HasOne(
            "entitlement_type",
            identity="entitlement_types",
            label="Entitlement Type",
            required=True,
        ),
        IntegerField("delta_granted", label="Delta Granted", required=True),
        IntegerField("max_rewards_per_actor", label="Max Rewards Per Actor", required=False),
        IntegerField("priority", label="Priority", required=True),
        IntegerEnumField("status", enum=GrowthRewardRuleStatus, label="Status", required=True),
        DateTimeField("starts_at", label="Starts At", required=False),
        DateTimeField("ends_at", label="Ends At", required=False),
        DateTimeField("created_at", label="Created At"),
        DateTimeField("updated_at", label="Updated At"),
    ]

    async def validate(self, request: Request, data: dict[str, Any]) -> None:
        try:
            trigger_event_value = int(data.get("trigger_event"))
        except Exception as exc:
            raise FormValidationError(
                {"trigger_event": "Trigger event must be an integer"}
            ) from exc
        if trigger_event_value not in (
            int(GrowthRewardTriggerEvent.INVITE_BIND_SUCCESS),
            int(GrowthRewardTriggerEvent.INVITEE_SETUP_COMPLETED),
            int(GrowthRewardTriggerEvent.CAMPAIGN_ATTRIBUTION_FIRST_TOUCH),
            int(GrowthRewardTriggerEvent.REDEEM_CODE_CLAIM_SUCCESS),
        ):
            raise FormValidationError({"trigger_event": "Invalid trigger event"})
        data["trigger_event"] = trigger_event_value

        try:
            scope_type_value = int(data.get("scope_type"))
        except Exception as exc:
            raise FormValidationError({"scope_type": "Scope type must be an integer"}) from exc
        if scope_type_value not in (
            int(GrowthRewardScopeType.GLOBAL),
            int(GrowthRewardScopeType.CAMPAIGN),
            int(GrowthRewardScopeType.REDEEM_BATCH),
        ):
            raise FormValidationError({"scope_type": "Invalid scope type"})
        data["scope_type"] = scope_type_value

        campaign_id = _extract_relation_id(data.get("campaign"))
        redeem_batch_id = _extract_relation_id(data.get("redeem_batch"))
        if scope_type_value == int(GrowthRewardScopeType.GLOBAL):
            if campaign_id is not None or redeem_batch_id is not None:
                raise FormValidationError(
                    {"scope_type": "Global scope must not select campaign or redeem batch"}
                )
            data["scope_id"] = 0
        elif scope_type_value == int(GrowthRewardScopeType.CAMPAIGN):
            if campaign_id is None:
                raise FormValidationError({"campaign": "Campaign is required for campaign scope"})
            if redeem_batch_id is not None:
                raise FormValidationError(
                    {"redeem_batch": "Redeem batch must be empty for campaign"}
                )
            data["scope_id"] = campaign_id
        else:
            if redeem_batch_id is None:
                raise FormValidationError(
                    {"redeem_batch": "Redeem batch is required for redeem-batch scope"}
                )
            if campaign_id is not None:
                raise FormValidationError(
                    {"campaign": "Campaign must be empty for redeem-batch scope"}
                )
            data["scope_id"] = redeem_batch_id

        if trigger_event_value in (
            int(GrowthRewardTriggerEvent.INVITE_BIND_SUCCESS),
            int(GrowthRewardTriggerEvent.INVITEE_SETUP_COMPLETED),
        ) and scope_type_value != int(GrowthRewardScopeType.GLOBAL):
            raise FormValidationError(
                {"scope_type": "Invite trigger events only support global scope"}
            )
        if trigger_event_value == int(
            GrowthRewardTriggerEvent.CAMPAIGN_ATTRIBUTION_FIRST_TOUCH
        ) and scope_type_value != int(GrowthRewardScopeType.CAMPAIGN):
            raise FormValidationError(
                {"scope_type": "Campaign attribution trigger must use campaign scope"}
            )
        if trigger_event_value == int(
            GrowthRewardTriggerEvent.REDEEM_CODE_CLAIM_SUCCESS
        ) and scope_type_value != int(GrowthRewardScopeType.REDEEM_BATCH):
            raise FormValidationError(
                {"scope_type": "Redeem claim trigger must use redeem-batch scope"}
            )

        entitlement_type_id = _extract_relation_id(data.get("entitlement_type"))
        if entitlement_type_id is None:
            raise FormValidationError({"entitlement_type": "Entitlement type is required"})
        data["entitlement_type_id"] = entitlement_type_id

        try:
            delta_granted_value = int(data.get("delta_granted"))
        except Exception as exc:
            raise FormValidationError(
                {"delta_granted": "Delta granted must be an integer"}
            ) from exc
        if delta_granted_value <= 0:
            raise FormValidationError({"delta_granted": "Delta granted must be greater than 0"})
        data["delta_granted"] = delta_granted_value

        max_rewards_raw = data.get("max_rewards_per_actor")
        if max_rewards_raw in (None, ""):
            data["max_rewards_per_actor"] = None
        else:
            try:
                max_rewards_value = int(max_rewards_raw)
            except Exception as exc:
                raise FormValidationError(
                    {"max_rewards_per_actor": "Max rewards must be an integer"}
                ) from exc
            if max_rewards_value <= 0:
                raise FormValidationError(
                    {"max_rewards_per_actor": "Max rewards per actor must be greater than 0"}
                )
            data["max_rewards_per_actor"] = max_rewards_value

        data["starts_at"] = _parse_datetime_field("starts_at", data.get("starts_at"))
        data["ends_at"] = _parse_datetime_field("ends_at", data.get("ends_at"))
        if (
            data["starts_at"] is not None
            and data["ends_at"] is not None
            and data["ends_at"] <= data["starts_at"]
        ):
            raise FormValidationError({"ends_at": "Ends at must be later than starts at"})

        await super().validate(request, data)

    async def before_create(
        self, request: Request, data: dict[str, Any], obj: GrowthRewardRule
    ) -> None:
        obj.scope_id = int(data["scope_id"])
        obj.entitlement_type_id = int(data["entitlement_type_id"])
        await super().before_create(request, data, obj)

    async def before_edit(
        self, request: Request, data: dict[str, Any], obj: GrowthRewardRule
    ) -> None:
        obj.scope_id = int(data["scope_id"])
        obj.entitlement_type_id = int(data["entitlement_type_id"])
        await super().before_edit(request, data, obj)

    def can_delete(self, request: Request) -> bool:
        return False


class GrowthRewardApplyView(BaseRoleAwareModelView):
    """Read-only admin view for growth_reward_applies."""

    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    searchable_fields = [
        "rule_id",
        "actor_user_id",
        "beneficiary_user_id",
        "source_type",
        "source_id",
        "idempotency_key",
    ]
    sortable_fields = [
        "id",
        "rule_id",
        "trigger_event",
        "target_role",
        "actor_user_id",
        "beneficiary_user_id",
        "source_type",
        "source_id",
        "created_at",
    ]
    fields_default_sort = [("created_at", True)]
    fields = [
        IntegerField("id", label="ID"),
        HasOne("rule", identity="growth_reward_rules", label="Rule", required=True),
        IntegerEnumField("trigger_event", enum=GrowthRewardTriggerEvent, label="Trigger Event"),
        IntegerEnumField("target_role", enum=GrowthRewardTargetRole, label="Target Role"),
        HasOne("actor_user", identity="user", label="Actor User", required=True),
        HasOne(
            "beneficiary_user",
            identity="user",
            label="Beneficiary User",
            required=True,
        ),
        StringField("source_type", label="Source Type"),
        IntegerField("source_id", label="Source ID"),
        IntegerEnumField("scope_type", enum=GrowthRewardScopeType, label="Scope Type"),
        IntegerField("scope_id", label="Scope ID"),
        HasOne(
            "entitlement_type",
            identity="entitlement_types",
            label="Entitlement Type",
            required=True,
        ),
        IntegerField("delta_granted", label="Delta Granted"),
        HasOne("ledger", identity="user_entitlement_ledger", label="Ledger", required=True),
        StringField("idempotency_key", label="Idempotency Key"),
        JSONField("event_payload", label="Event Payload", required=False),
        DateTimeField("created_at", label="Created At"),
    ]


class RedeemCodeBatchView(BaseRoleAwareModelView):
    """Admin view for redeem_code_batches."""

    exclude_fields_from_create = ["id", "created_at", "updated_at", "budget_used"]
    exclude_fields_from_edit = ["id", "created_at", "updated_at", "budget_used"]
    searchable_fields = ["batch_code", "name"]
    sortable_fields = [
        "id",
        "batch_code",
        "name",
        "status",
        "mode",
        "budget_total",
        "budget_used",
        "created_at",
        "updated_at",
    ]
    fields_default_sort = [("created_at", True)]
    fields = [
        IntegerField("id", label="ID"),
        StringField("batch_code", label="Batch Code", required=True),
        StringField("name", label="Name", required=True),
        StringField("description", label="Description", required=False),
        IntegerEnumField("status", enum=RedeemCodeBatchStatus, label="Status", required=True),
        IntegerEnumField("mode", enum=RedeemCodeMode, label="Mode", required=True),
        IntegerField("budget_total", label="Budget Total", required=False),
        IntegerField("budget_used", label="Budget Used", required=False),
        IntegerField("max_claims_per_user", label="Max Claims Per User", required=True),
        DateTimeField("starts_at", label="Starts At", required=False),
        DateTimeField("ends_at", label="Ends At", required=False),
        DateTimeField("created_at", label="Created At"),
        DateTimeField("updated_at", label="Updated At"),
    ]

    def can_delete(self, request: Request) -> bool:
        return False


class RedeemCodeView(BaseRoleAwareModelView):
    """Admin view for redeem_codes."""

    exclude_fields_from_create = ["id", "batch_id", "created_at", "updated_at", "claimed_total"]
    exclude_fields_from_edit = ["id", "batch_id", "created_at", "updated_at", "claimed_total"]
    searchable_fields = ["code", "batch_id"]
    sortable_fields = [
        "id",
        "batch_id",
        "code",
        "status",
        "max_claims_total",
        "claimed_total",
        "created_at",
        "updated_at",
    ]
    fields_default_sort = [("created_at", True)]
    fields = [
        IntegerField("id", label="ID"),
        HasOne("batch", identity="redeem_code_batches", label="Batch", required=True),
        StringField("code", label="Redeem Code", required=True),
        IntegerEnumField("status", enum=RedeemCodeStatus, label="Status", required=True),
        IntegerField("max_claims_total", label="Max Claims Total", required=False),
        IntegerField("claimed_total", label="Claimed Total", required=False),
        DateTimeField("starts_at", label="Starts At", required=False),
        DateTimeField("ends_at", label="Ends At", required=False),
        DateTimeField("created_at", label="Created At"),
        DateTimeField("updated_at", label="Updated At"),
    ]

    async def validate(self, request: Request, data: dict[str, Any]) -> None:
        batch_id = _extract_relation_id(data.get("batch"))
        if batch_id is None:
            raise FormValidationError({"batch": "Batch is required"})
        data["batch_id"] = batch_id

        code = str(data.get("code", "")).strip().upper()
        if code == "":
            raise FormValidationError({"code": "Redeem code is required"})
        if len(code) < REDEEM_CODE_MIN_LENGTH or len(code) > REDEEM_CODE_MAX_LENGTH:
            raise FormValidationError({"code": "Redeem code length must be between 4 and 32"})
        if not code.isascii() or any(
            not (char.isdigit() or char.isupper() or char == "-") for char in code
        ):
            raise FormValidationError({"code": "Redeem code must contain only A-Z, 0-9 and -"})
        data["code"] = code

        try:
            status_value = int(data.get("status"))
        except Exception as exc:
            raise FormValidationError({"status": "Status must be an integer"}) from exc
        if status_value not in (int(RedeemCodeStatus.ACTIVE), int(RedeemCodeStatus.INACTIVE)):
            raise FormValidationError({"status": "Invalid status"})
        data["status"] = status_value

        max_claims_raw = data.get("max_claims_total")
        if max_claims_raw in (None, ""):
            data["max_claims_total"] = None
        else:
            try:
                max_claims_value = int(max_claims_raw)
            except Exception as exc:
                raise FormValidationError(
                    {"max_claims_total": "Max claims total must be an integer"}
                ) from exc
            if max_claims_value <= 0:
                raise FormValidationError(
                    {"max_claims_total": "Max claims total must be greater than 0"}
                )
            data["max_claims_total"] = max_claims_value

        data["starts_at"] = _parse_datetime_field("starts_at", data.get("starts_at"))
        data["ends_at"] = _parse_datetime_field("ends_at", data.get("ends_at"))
        if (
            data["starts_at"] is not None
            and data["ends_at"] is not None
            and data["ends_at"] <= data["starts_at"]
        ):
            raise FormValidationError({"ends_at": "Ends at must be later than starts at"})

        await super().validate(request, data)

    async def before_create(self, request: Request, data: dict[str, Any], obj: RedeemCode) -> None:
        obj.batch_id = int(data["batch_id"])
        await super().before_create(request, data, obj)

    async def before_edit(self, request: Request, data: dict[str, Any], obj: RedeemCode) -> None:
        obj.batch_id = int(data["batch_id"])
        await super().before_edit(request, data, obj)

    def can_delete(self, request: Request) -> bool:
        return False


class RedeemCodeClaimView(BaseRoleAwareModelView):
    """Read-only admin view for redeem_code_claims."""

    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    searchable_fields = ["user_id", "redeem_code_id", "batch_id", "code_snapshot"]
    sortable_fields = ["id", "user_id", "redeem_code_id", "batch_id", "created_at"]
    fields_default_sort = [("created_at", True)]
    fields = [
        IntegerField("id", label="ID"),
        HasOne("user", identity="user", label="User", required=True),
        HasOne("redeem_code", identity="redeem_codes", label="Redeem Code", required=True),
        HasOne("batch", identity="redeem_code_batches", label="Batch", required=True),
        StringField("code_snapshot", label="Code Snapshot"),
        StringField("idempotency_key", label="Idempotency Key"),
        JSONField("event_payload", label="Event Payload", required=False),
        DateTimeField("created_at", label="Created At"),
    ]


invite_code_view = InviteCodeView(
    InviteCode, name="Invite Codes", icon="fa fa-ticket", identity="invite_codes"
)
invite_binding_view = InviteBindingView(
    InviteBinding, name="Invite Bindings", icon="fa fa-link", identity="invite_bindings"
)
invite_event_view = InviteEventView(
    InviteEvent, name="Invite Events", icon="fa fa-history", identity="invite_events"
)
invite_recognition_log_view = InviteRecognitionLogView(
    InviteRecognitionLog,
    name="Invite Recognition Logs",
    icon="fa fa-clipboard-list",
    identity="invite_recognition_logs",
)
invite_share_template_view = InviteShareTemplateView(
    InviteShareTemplate,
    name="Invite Share Templates",
    icon="fa fa-comment-dots",
    identity="invite_share_templates",
)
campaign_view = CampaignView(
    Campaign, name="Campaigns", icon="fa fa-bullhorn", identity="campaigns"
)
campaign_attribution_view = CampaignAttributionView(
    CampaignAttribution,
    name="Growth",
    icon="fa fa-location-arrow",
    identity="campaign_attributions",
)
growth_reward_rule_view = GrowthRewardRuleView(
    GrowthRewardRule,
    name="Reward Rules",
    icon="fa fa-sitemap",
    identity="growth_reward_rules",
)
growth_reward_apply_view = GrowthRewardApplyView(
    GrowthRewardApply,
    name="Reward Applies",
    icon="fa fa-list",
    identity="growth_reward_applies",
)
redeem_code_batch_view = RedeemCodeBatchView(
    RedeemCodeBatch,
    name="Redeem Code Batches",
    icon="fa fa-layer-group",
    identity="redeem_code_batches",
)
redeem_code_view = RedeemCodeView(
    RedeemCode, name="Redeem Codes", icon="fa fa-key", identity="redeem_codes"
)
redeem_code_claim_view = RedeemCodeClaimView(
    RedeemCodeClaim, name="Redeem Claims", icon="fa fa-receipt", identity="redeem_code_claims"
)

GROWTH_MODEL_VIEWS = [
    campaign_view,
    campaign_attribution_view,
    growth_reward_rule_view,
    growth_reward_apply_view,
    redeem_code_batch_view,
    redeem_code_view,
    redeem_code_claim_view,
    invite_code_view,
    invite_binding_view,
    invite_event_view,
    invite_recognition_log_view,
    invite_share_template_view,
]
