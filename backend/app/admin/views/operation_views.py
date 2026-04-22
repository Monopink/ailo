"""Operation content model views for Starlette-Admin."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, cast

from starlette.requests import Request
from starlette_admin import DateTimeField, HasOne, IntegerField, StringField
from starlette_admin.exceptions import FormValidationError

from app.admin.views.base import BaseRoleAwareModelView, IntegerEnumField
from app.enums.invite import OperationAssetType, OperationStatus
from app.models.invite import OperationAsset, OperationPublishLog, OperationSlotConfig

SLOT_CODE_PATTERN = re.compile(r"^[a-z0-9_\\-]{1,64}$")
CHANNEL_PATTERN = re.compile(r"^[a-z0-9_\\-]{1,32}$")


def _extract_relation_id(value: object) -> int | None:
    """Extract a relation primary key from a HasOne field value."""
    relation_id = getattr(value, "id", value)
    if relation_id is None:
        return None
    try:
        return int(cast(Any, relation_id))
    except (TypeError, ValueError):
        return None


def _resolve_admin_user_id(request: Request) -> int | None:
    """Resolve current admin user id from session payload."""
    if not hasattr(request, "session"):
        return None
    admin_user = request.session.get("admin_user")
    if not isinstance(admin_user, dict):
        return None
    raw_id = admin_user.get("id")
    if raw_id is None or not isinstance(raw_id, str | int):
        return None
    try:
        return int(raw_id)
    except (TypeError, ValueError):
        return None


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


class OperationAssetView(BaseRoleAwareModelView):
    """Admin view for operation_assets."""

    searchable_fields = ["asset_code", "cdn_url"]
    sortable_fields = [
        "id",
        "asset_code",
        "asset_type",
        "status",
        "version",
        "created_at",
        "updated_at",
    ]
    fields_default_sort = [("id", True)]
    fields = [
        IntegerField("id", label="ID"),
        StringField("asset_code", label="Asset Code", required=True),
        HasOne("media_file", identity="media_file", label="Media File", required=False),
        IntegerEnumField("asset_type", enum=OperationAssetType, label="Asset Type", required=True),
        StringField("cdn_url", label="CDN URL", required=True),
        StringField("mime_type", label="MIME Type", required=False),
        IntegerField("width", label="Width", required=False),
        IntegerField("height", label="Height", required=False),
        IntegerEnumField("status", enum=OperationStatus, label="Status", required=True),
        IntegerField("version", label="Version", required=True),
        DateTimeField("created_at", label="Created At"),
        DateTimeField("updated_at", label="Updated At"),
    ]
    exclude_fields_from_create = ["id", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "created_at", "updated_at"]

    async def validate(self, request: Request, data: dict[str, Any]) -> None:
        asset_code = str(data.get("asset_code", "")).strip()
        if SLOT_CODE_PATTERN.fullmatch(asset_code) is None:
            raise FormValidationError({"asset_code": "Asset code format is invalid"})
        data["asset_code"] = asset_code

        try:
            asset_type_value = int(data.get("asset_type"))
        except Exception as exc:
            raise FormValidationError({"asset_type": "Asset type must be an integer"}) from exc
        if asset_type_value != int(OperationAssetType.IMAGE):
            raise FormValidationError({"asset_type": "Only image asset type is supported"})
        data["asset_type"] = asset_type_value

        cdn_url = str(data.get("cdn_url", "")).strip()
        if not cdn_url.startswith("https://"):
            raise FormValidationError({"cdn_url": "CDN URL must start with https://"})
        data["cdn_url"] = cdn_url

        mime_type = data.get("mime_type")
        if mime_type in (None, ""):
            data["mime_type"] = None
        else:
            data["mime_type"] = str(mime_type).strip()

        for field_name in ("width", "height", "version"):
            raw_value = data.get(field_name)
            if field_name in ("width", "height") and raw_value in (None, ""):
                data[field_name] = None
                continue
            try:
                value = int(raw_value)
            except Exception as exc:
                raise FormValidationError({field_name: f"{field_name} must be an integer"}) from exc
            if value <= 0:
                raise FormValidationError({field_name: f"{field_name} must be greater than 0"})
            data[field_name] = value

        media_file_id = _extract_relation_id(data.get("media_file"))
        data["media_file_id"] = media_file_id

        try:
            status_value = int(data.get("status"))
        except Exception as exc:
            raise FormValidationError({"status": "Status must be an integer"}) from exc
        if status_value not in (int(OperationStatus.ACTIVE), int(OperationStatus.INACTIVE)):
            raise FormValidationError({"status": "Invalid status"})
        data["status"] = status_value

        await super().validate(request, data)

    async def before_create(
        self, request: Request, data: dict[str, Any], obj: OperationAsset
    ) -> None:
        obj.media_file_id = data.get("media_file_id")
        await super().before_create(request, data, obj)

    async def before_edit(
        self, request: Request, data: dict[str, Any], obj: OperationAsset
    ) -> None:
        obj.media_file_id = data.get("media_file_id")
        await super().before_edit(request, data, obj)

    def can_delete(self, request: Request) -> bool:
        return False


class OperationSlotConfigView(BaseRoleAwareModelView):
    """Admin view for operation_slot_configs."""

    searchable_fields = ["slot_code", "channel", "title", "path_template"]
    sortable_fields = [
        "id",
        "slot_code",
        "channel",
        "priority",
        "status",
        "version",
        "created_at",
        "updated_at",
    ]
    fields_default_sort = [("priority", False), ("id", True)]
    fields = [
        IntegerField("id", label="ID"),
        StringField("slot_code", label="Slot Code", required=True),
        StringField("channel", label="Channel", required=True),
        StringField("title", label="Title", required=True),
        StringField("path_template", label="Path Template", required=True),
        HasOne("asset", identity="operation_assets", label="Asset", required=True),
        IntegerField("priority", label="Priority", required=True),
        DateTimeField("start_at", label="Start At", required=False),
        DateTimeField("end_at", label="End At", required=False),
        IntegerEnumField("status", enum=OperationStatus, label="Status", required=True),
        IntegerField("version", label="Version", required=True),
        DateTimeField("created_at", label="Created At"),
        DateTimeField("updated_at", label="Updated At"),
    ]
    exclude_fields_from_create = ["id", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "created_at", "updated_at"]

    async def validate(self, request: Request, data: dict[str, Any]) -> None:
        slot_code = str(data.get("slot_code", "")).strip()
        if SLOT_CODE_PATTERN.fullmatch(slot_code) is None:
            raise FormValidationError({"slot_code": "Slot code format is invalid"})
        data["slot_code"] = slot_code

        channel = str(data.get("channel", "")).strip()
        if CHANNEL_PATTERN.fullmatch(channel) is None:
            raise FormValidationError({"channel": "Channel format is invalid"})
        data["channel"] = channel

        title = str(data.get("title", "")).strip()
        if title == "":
            raise FormValidationError({"title": "Title is required"})
        data["title"] = title

        path_template = str(data.get("path_template", "")).strip()
        if not path_template.startswith("/"):
            raise FormValidationError({"path_template": "Path template must start with /"})
        data["path_template"] = path_template

        asset_id = _extract_relation_id(data.get("asset"))
        if asset_id is None:
            raise FormValidationError({"asset": "Asset is required"})
        data["asset_id"] = asset_id

        for field_name in ("priority", "version"):
            try:
                value = int(data.get(field_name))
            except Exception as exc:
                raise FormValidationError({field_name: f"{field_name} must be an integer"}) from exc
            if value <= 0:
                raise FormValidationError({field_name: f"{field_name} must be greater than 0"})
            data[field_name] = value

        data["start_at"] = _parse_datetime_field("start_at", data.get("start_at"))
        data["end_at"] = _parse_datetime_field("end_at", data.get("end_at"))
        if (
            data["start_at"] is not None
            and data["end_at"] is not None
            and data["end_at"] <= data["start_at"]
        ):
            raise FormValidationError({"end_at": "End at must be later than start at"})

        try:
            status_value = int(data.get("status"))
        except Exception as exc:
            raise FormValidationError({"status": "Status must be an integer"}) from exc
        if status_value not in (int(OperationStatus.ACTIVE), int(OperationStatus.INACTIVE)):
            raise FormValidationError({"status": "Invalid status"})
        data["status"] = status_value

        await super().validate(request, data)

    async def before_create(
        self, request: Request, data: dict[str, Any], obj: OperationSlotConfig
    ) -> None:
        obj.asset_id = int(data["asset_id"])
        await super().before_create(request, data, obj)

    async def before_edit(
        self, request: Request, data: dict[str, Any], obj: OperationSlotConfig
    ) -> None:
        obj.asset_id = int(data["asset_id"])
        await super().before_edit(request, data, obj)

    async def create(self, request: Request, data: dict[str, Any]) -> Any:
        """Create slot config and append publish log when active."""
        obj = await super().create(request, data)
        if int(getattr(obj, "status", 0)) == int(OperationStatus.ACTIVE):
            request.state.session.add(
                OperationPublishLog(
                    slot_code=str(getattr(obj, "slot_code", "") or ""),
                    action="publish",
                    from_version=None,
                    to_version=int(getattr(obj, "version", 0) or 0),
                    operator_id=_resolve_admin_user_id(request),
                    reason="admin_create_active_slot_config",
                )
            )
            await request.state.session.flush()
        return obj

    async def edit(self, request: Request, pk: Any, data: dict[str, Any]) -> Any:
        """Edit slot config and append publish log when active."""
        old_obj = await self.find_by_pk(request, pk)
        from_version: int | None = None
        if old_obj is not None:
            try:
                from_version = int(old_obj.version)
            except (TypeError, ValueError):
                from_version = None

        obj = await super().edit(request, pk, data)
        if int(getattr(obj, "status", 0)) == int(OperationStatus.ACTIVE):
            request.state.session.add(
                OperationPublishLog(
                    slot_code=str(getattr(obj, "slot_code", "") or ""),
                    action="publish",
                    from_version=from_version,
                    to_version=int(getattr(obj, "version", 0) or 0),
                    operator_id=_resolve_admin_user_id(request),
                    reason="admin_update_active_slot_config",
                )
            )
            await request.state.session.flush()
        return obj

    def can_delete(self, request: Request) -> bool:
        return False


class OperationPublishLogView(BaseRoleAwareModelView):
    """Read-only admin view for operation_publish_logs."""

    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    searchable_fields = ["slot_code", "action", "reason"]
    sortable_fields = ["id", "slot_code", "action", "from_version", "to_version", "created_at"]
    fields_default_sort = [("created_at", True)]
    fields = [
        IntegerField("id", label="ID"),
        StringField("slot_code", label="Slot Code"),
        StringField("action", label="Action"),
        IntegerField("from_version", label="From Version", required=False),
        IntegerField("to_version", label="To Version"),
        HasOne("operator", identity="admin_user", label="Operator", required=False),
        StringField("reason", label="Reason", required=False),
        DateTimeField("created_at", label="Created At"),
    ]


operation_asset_view = OperationAssetView(
    OperationAsset,
    name="Operation Assets",
    icon="fa fa-image",
    identity="operation_assets",
)
operation_slot_config_view = OperationSlotConfigView(
    OperationSlotConfig,
    name="Operation Slot Configs",
    icon="fa fa-map-pin",
    identity="operation_slot_configs",
)
operation_publish_log_view = OperationPublishLogView(
    OperationPublishLog,
    name="Operation Publish Logs",
    icon="fa fa-history",
    identity="operation_publish_logs",
)

OPERATION_MODEL_VIEWS = [
    operation_asset_view,
    operation_slot_config_view,
    operation_publish_log_view,
]
