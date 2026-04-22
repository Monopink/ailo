"""Custom admin view for entitlement operations."""

from __future__ import annotations

from sqlalchemy import select
from starlette.requests import Request
from starlette.responses import Response
from starlette.templating import Jinja2Templates
from starlette_admin import CustomView

from app.enums import AdminRole
from app.models.entitlement import EntitlementReasonCode, EntitlementType, UserEntitlementLedger
from app.services.entitlement.service import (
    ENTITLEMENT_SOURCE_ADMIN_MANUAL_ADJUST,
    ENTITLEMENT_SOURCE_ADMIN_MANUAL_GRANT,
)


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

    def is_active(self, request: Request) -> bool:
        path = request.scope["path"]
        admin_state = getattr(request.app.state, "ADMIN", None)
        if admin_state and hasattr(admin_state, "base_url"):
            return path == f"{admin_state.base_url}{self.path}"
        return path.endswith(self.path)

    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        db = request.state.session

        entitlement_types_stmt = (
            select(EntitlementType)
            .where(EntitlementType.status == 1)
            .order_by(EntitlementType.code.asc())
        )
        reason_codes_stmt = (
            select(EntitlementReasonCode)
            .where(EntitlementReasonCode.status == 1)
            .order_by(EntitlementReasonCode.is_system.desc(), EntitlementReasonCode.code.asc())
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
            .limit(30)
        )

        entitlement_types_result = await db.execute(entitlement_types_stmt)
        reason_codes_result = await db.execute(reason_codes_stmt)
        latest_ops_result = await db.execute(latest_ops_stmt)

        entitlement_types = [
            {
                "code": row.code,
                "mode": int(row.mode),
                "unit": row.unit,
            }
            for row in entitlement_types_result.scalars().all()
        ]
        reason_codes = [
            {
                "code": row.code,
                "display_name": row.display_name,
                "is_system": bool(row.is_system),
            }
            for row in reason_codes_result.scalars().all()
        ]
        latest_operations = [
            {
                "id": int(row.id),
                "user_id": int(row.user_id),
                "entitlement_type_id": int(row.entitlement_type_id),
                "action_type": int(row.action_type),
                "delta_granted": int(row.delta_granted),
                "source_type": row.source_type,
                "reason_code": row.reason_code,
                "operator_admin_user_id": row.operator_admin_user_id,
                "idempotency_key": row.idempotency_key,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in latest_ops_result.scalars().all()
        ]

        context = {
            "request": request,
            "operations_api_path": "/admin-api/entitlements/operations",
            "entitlement_types": entitlement_types,
            "reason_codes": reason_codes,
            "latest_operations": latest_operations,
            "can_operate": self._can_operate(request),
        }
        return templates.TemplateResponse("custom_views/entitlement_operations.html", context)


entitlement_operation_view = EntitlementOperationView(
    label="Entitlement Operations",
    icon="fa fa-sliders",
    path="/entitlement-operations",
)
