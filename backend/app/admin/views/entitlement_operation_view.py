"""Custom admin view for entitlement operations."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from starlette.requests import Request
from starlette.responses import Response
from starlette.templating import Jinja2Templates
from starlette_admin import CustomView

from app.enums import AdminRole
from app.models.entitlement import (
    EntitlementReasonCode,
    EntitlementType,
    UserEntitlementAccount,
    UserEntitlementLedger,
)
from app.models.user import User
from app.services.entitlement.service import (
    ENTITLEMENT_ACTION_ADJUST,
    ENTITLEMENT_ACTION_GRANT,
    ENTITLEMENT_SOURCE_ADMIN_MANUAL_ADJUST,
    ENTITLEMENT_SOURCE_ADMIN_MANUAL_GRANT,
)
from app.utils.user_display import build_masked_user_display_label

_ZH_CHAR_PATTERN = re.compile(r"[\u4e00-\u9fff]")

_ENTITLEMENT_TYPE_ZH_NAME_BY_CODE: dict[str, str] = {
    "ai_contact_limit": "AI联系人上限",
}

_REASON_CODE_ZH_NAME_BY_CODE: dict[str, str] = {
    "admin_activity_reward": "活动奖励补发",
    "admin_bug_compensation": "问题补偿",
    "admin_customer_care": "客服补偿",
    "admin_ops_correction": "运营修正",
    "admin_penalty_deduction": "违规惩罚扣减",
    "admin_abuse_control": "风控滥用收回",
}


class EntitlementOperationView(CustomView):
    """Render manual entitlement operation console."""

    @staticmethod
    def _can_operate(request: Request) -> bool:
        admin_user = request.session.get("admin_user") if hasattr(request, "session") else None
        if not isinstance(admin_user, dict):
            return False
        try:
            role_value = int(admin_user.get("role"))
        except Exception:
            return False
        return role_value in (int(AdminRole.SUPER_ADMIN), int(AdminRole.ADMIN))

    @staticmethod
    def _extract_selected_entitlement_type_code(
        request: Request, *, entitlement_types: list[EntitlementType]
    ) -> str | None:
        selected_code = str(request.query_params.get("entitlement_type_code", "")).strip()
        if selected_code == "":
            return None
        available_codes = {row.code for row in entitlement_types}
        return selected_code if selected_code in available_codes else None

    @staticmethod
    def _parse_positive_int(raw_value: str | None) -> int | None:
        if raw_value is None:
            return None
        value = raw_value.strip()
        if value == "":
            return None
        try:
            parsed = int(value)
        except ValueError:
            return None
        return parsed if parsed > 0 else None

    @staticmethod
    def _resolve_action_label(action_type: int) -> str:
        if action_type == ENTITLEMENT_ACTION_GRANT:
            return "grant"
        if action_type == ENTITLEMENT_ACTION_ADJUST:
            return "adjust"
        return str(action_type)

    @staticmethod
    def _resolve_type_display_name(row: EntitlementType) -> str:
        code = row.code
        raw_name = getattr(row, "display_name", None)
        if isinstance(raw_name, str) and raw_name.strip() != "":
            normalized = raw_name.strip()
            if _ZH_CHAR_PATTERN.search(normalized):
                return normalized
            if code in _ENTITLEMENT_TYPE_ZH_NAME_BY_CODE:
                return _ENTITLEMENT_TYPE_ZH_NAME_BY_CODE[code]
            return normalized
        return _ENTITLEMENT_TYPE_ZH_NAME_BY_CODE.get(code, code)

    @staticmethod
    def _resolve_reason_display_name(row: EntitlementReasonCode) -> str:
        code = row.code
        raw_name = getattr(row, "display_name", None)
        if isinstance(raw_name, str) and raw_name.strip() != "":
            normalized = raw_name.strip()
            if _ZH_CHAR_PATTERN.search(normalized):
                return normalized
            if code in _REASON_CODE_ZH_NAME_BY_CODE:
                return _REASON_CODE_ZH_NAME_BY_CODE[code]
            return normalized
        return _REASON_CODE_ZH_NAME_BY_CODE.get(code, code)

    def is_active(self, request: Request) -> bool:
        path = request.scope["path"]
        admin_state = getattr(request.app.state, "ADMIN", None)
        if admin_state and hasattr(admin_state, "base_url"):
            return path == f"{admin_state.base_url}{self.path}"
        return path.endswith(self.path)

    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        db = request.state.session

        entitlement_types_result = await db.execute(
            select(EntitlementType)
            .where(EntitlementType.status == 1)
            .order_by(EntitlementType.code.asc())
        )
        reason_codes_result = await db.execute(
            select(EntitlementReasonCode)
            .where(EntitlementReasonCode.status == 1)
            .order_by(EntitlementReasonCode.is_system.desc(), EntitlementReasonCode.code.asc())
        )
        entitlement_type_rows = list(entitlement_types_result.scalars().all())
        entitlement_type_id_by_code: dict[str, int] = {
            row.code: int(row.id) for row in entitlement_type_rows
        }
        entitlement_type_codes = set(entitlement_type_id_by_code.keys())

        preset_user_id = self._parse_positive_int(request.query_params.get("preset_user_id"))
        preset_entitlement_type_code_raw = str(
            request.query_params.get("preset_entitlement_type_code", "")
        ).strip()
        preset_entitlement_type_code = (
            preset_entitlement_type_code_raw
            if preset_entitlement_type_code_raw in entitlement_type_codes
            else None
        )
        preset_account_id = self._parse_positive_int(request.query_params.get("preset_account_id"))
        if preset_account_id is not None:
            preset_account_stmt = (
                select(UserEntitlementAccount.user_id, EntitlementType.code)
                .join(
                    EntitlementType,
                    EntitlementType.id == UserEntitlementAccount.entitlement_type_id,
                )
                .where(UserEntitlementAccount.id == preset_account_id)
                .limit(1)
            )
            preset_account_result = await db.execute(preset_account_stmt)
            preset_account_row = preset_account_result.one_or_none()
            if preset_account_row is not None:
                preset_user_id = int(preset_account_row[0])
                candidate_code = str(preset_account_row[1])
                if candidate_code in entitlement_type_codes:
                    preset_entitlement_type_code = candidate_code

        preset_user_option: dict[str, object] | None = None
        if preset_user_id is not None:
            preset_user_stmt = (
                select(User.id, User.username, User.phone, User.email)
                .where(User.id == preset_user_id)
                .limit(1)
            )
            preset_user_result = await db.execute(preset_user_stmt)
            preset_user_row = preset_user_result.one_or_none()
            if preset_user_row is not None:
                preset_user_option = {
                    "id": str(int(preset_user_row[0])),
                    "text": build_masked_user_display_label(
                        user_id=int(preset_user_row[0]),
                        username=preset_user_row[1]
                        if isinstance(preset_user_row[1], str)
                        else None,
                        phone=preset_user_row[2] if isinstance(preset_user_row[2], str) else None,
                        email=preset_user_row[3] if isinstance(preset_user_row[3], str) else None,
                    ),
                }

        selected_entitlement_type_code = self._extract_selected_entitlement_type_code(
            request, entitlement_types=entitlement_type_rows
        )
        if selected_entitlement_type_code is None and preset_entitlement_type_code is not None:
            selected_entitlement_type_code = preset_entitlement_type_code
        selected_entitlement_type_id = (
            entitlement_type_id_by_code[selected_entitlement_type_code]
            if selected_entitlement_type_code is not None
            else None
        )

        latest_ops_stmt = (
            select(UserEntitlementLedger)
            .where(
                UserEntitlementLedger.source_type.in_(
                    [
                        ENTITLEMENT_SOURCE_ADMIN_MANUAL_GRANT,
                        ENTITLEMENT_SOURCE_ADMIN_MANUAL_ADJUST,
                    ]
                )
            )
            .order_by(UserEntitlementLedger.created_at.desc())
            .limit(50)
        )
        if selected_entitlement_type_id is not None:
            latest_ops_stmt = latest_ops_stmt.where(
                UserEntitlementLedger.entitlement_type_id == selected_entitlement_type_id
            )
        latest_ops_result = await db.execute(latest_ops_stmt)

        entitlement_type_meta: dict[int, dict[str, Any]] = {
            int(row.id): {
                "code": row.code,
                "mode": int(row.mode),
                "unit": row.unit,
                "display_name": self._resolve_type_display_name(row),
            }
            for row in entitlement_type_rows
        }

        entitlement_types = [
            {
                "id": int(row.id),
                "code": row.code,
                "mode": int(row.mode),
                "unit": row.unit,
                "display_name": self._resolve_type_display_name(row),
            }
            for row in entitlement_type_rows
        ]
        reason_codes = [
            {
                "code": row.code,
                "display_name": self._resolve_reason_display_name(row),
                "applies_to": str(getattr(row, "applies_to", "both") or "both").strip().lower(),
                "is_system": bool(row.is_system),
            }
            for row in reason_codes_result.scalars().all()
        ]
        reason_display_name_by_code = {
            str(item["code"]): str(item["display_name"]) for item in reason_codes
        }
        latest_operations = [
            {
                "id": int(row.id),
                "user_id": int(row.user_id),
                "entitlement_type_code": entitlement_type_meta.get(
                    int(row.entitlement_type_id), {}
                ).get("code", "-"),
                "entitlement_type_display_name": entitlement_type_meta.get(
                    int(row.entitlement_type_id), {}
                ).get("display_name", "-"),
                "action_type": int(row.action_type),
                "action_label": self._resolve_action_label(int(row.action_type)),
                "delta_granted": int(row.delta_granted),
                "source_type": row.source_type,
                "reason_code": row.reason_code,
                "reason_display_name": reason_display_name_by_code.get(str(row.reason_code or "")),
                "operator_admin_user_id": row.operator_admin_user_id,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in latest_ops_result.scalars().all()
        ]

        context = {
            "request": request,
            "operations_api_path": "/admin-api/entitlements/operations",
            "user_search_api_path": "/admin-api/entitlements/users/search",
            "user_assets_api_path": "/admin-api/entitlements/users/assets",
            "account_snapshot_api_path": "/admin-api/entitlements/account-snapshot",
            "entitlement_types": entitlement_types,
            "reason_codes": reason_codes,
            "latest_operations": latest_operations,
            "selected_entitlement_type_code": selected_entitlement_type_code,
            "preset_entitlement_type_code": preset_entitlement_type_code,
            "preset_user_option": preset_user_option,
            "can_operate": self._can_operate(request),
        }
        return templates.TemplateResponse("custom_views/entitlement_operations.html", context)


entitlement_operation_view = EntitlementOperationView(
    label="Entitlement Operations",
    icon="fa fa-sliders",
    path="/entitlement-operations",
)
