"""Security management admin APIs for manual IP block operations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, verify_admin_session
from app.enums import AdminOperationType, AdminRole, IPBlockStatus
from app.models.security import SecurityIPBlock
from app.services.security.ip_block_admin_service import release_ip_block, upsert_manual_ip_block
from app.services.security.ip_network_target import normalize_stored_network
from app.utils.admin_logs import create_operation_log
from app.utils.logging import get_logger

logger = get_logger(__name__)

security_management_router = APIRouter(prefix="/security")
_PERMANENT_EXPIRES_YEAR_THRESHOLD = 9999


class ManualIPBlockUpsertRequest(BaseModel):
    """Payload for creating/updating a manual IP block."""

    target: str = Field(min_length=1, max_length=64)
    severity_level: int = Field(ge=1, le=4)
    reason: str = Field(min_length=1, max_length=500)
    is_permanent: bool = False
    ttl_seconds: int | None = Field(default=None, ge=1)


class ManualIPBlockReleaseRequest(BaseModel):
    """Payload for releasing a manual IP block."""

    release_reason: str = Field(min_length=1, max_length=128)


def _extract_admin_role(admin_user: dict[str, Any]) -> int:
    role_raw = admin_user.get("role")
    if isinstance(role_raw, bool) or not isinstance(role_raw, int | str):
        raise HTTPException(status_code=403, detail="Permission denied")
    try:
        role = int(role_raw)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=403, detail="Permission denied") from exc
    if role not in (int(AdminRole.SUPER_ADMIN), int(AdminRole.ADMIN), int(AdminRole.VIEWER)):
        raise HTTPException(status_code=403, detail="Permission denied")
    return role


def _require_admin_write_role(admin_user: dict[str, Any]) -> int:
    role = _extract_admin_role(admin_user)
    if role not in (int(AdminRole.SUPER_ADMIN), int(AdminRole.ADMIN)):
        raise HTTPException(status_code=403, detail="Permission denied")
    return role


def _map_validation_error(error_code: str) -> str:
    mapping = {
        "target_required": "封禁目标不能为空",
        "target_invalid_ip": "IP 格式不合法",
        "target_invalid_cidr": "CIDR 格式不合法",
        "ttl_required": "临时封禁必须填写有效时长",
        "ttl_invalid": "临时时长必须大于 0",
        "reason_required": "封禁原因不能为空",
        "release_reason_required": "解封原因不能为空",
        "severity_level_invalid": "严重级别不合法",
        "block_not_found": "封禁记录不存在",
        "block_not_active": "封禁记录不是生效状态",
        "block_not_effective": "封禁记录已失效，不能解封",
    }
    return mapping.get(error_code, "请求参数不合法")


def _serialize_ip_block(row: SecurityIPBlock) -> dict[str, object]:
    normalized_target = normalize_stored_network(str(row.target_network))
    is_permanent = row.expires_at.year >= _PERMANENT_EXPIRES_YEAR_THRESHOLD
    return {
        "id": int(row.id),
        "target": normalized_target.display_target,
        "target_type": normalized_target.target_type,
        "status": int(row.status),
        "severity_level": int(row.severity_level),
        "reason_code": row.reason_code,
        "rule_code": row.rule_code,
        "rule_version": row.rule_version,
        "source": row.source,
        "request_path": row.request_path,
        "request_method": row.request_method,
        "evidence_payload": row.evidence_payload,
        "hit_count": int(row.hit_count),
        "blocked_at": row.blocked_at.isoformat() if row.blocked_at else None,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "released_at": row.released_at.isoformat() if row.released_at else None,
        "release_reason": row.release_reason,
        "is_permanent": is_permanent,
    }


def _target_type_from_row(row: SecurityIPBlock) -> str:
    return normalize_stored_network(str(row.target_network)).target_type


@security_management_router.get("/ip-blocks")
async def list_ip_blocks(
    status: str = Query(default="active", pattern="^(active|released|all)$"),
    limit: int = Query(default=100, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    admin_user: dict[str, Any] = Depends(verify_admin_session),
) -> dict[str, object]:
    """List IP block records for manual management view."""
    _extract_admin_role(admin_user)

    now = datetime.now(UTC)
    stmt = select(SecurityIPBlock)
    if status == "active":
        stmt = stmt.where(
            and_(
                SecurityIPBlock.status == int(IPBlockStatus.ACTIVE),
                SecurityIPBlock.expires_at > now,
            )
        )
    elif status == "released":
        stmt = stmt.where(SecurityIPBlock.status == int(IPBlockStatus.RELEASED))
    else:
        stmt = stmt.where(
            or_(
                and_(
                    SecurityIPBlock.status == int(IPBlockStatus.ACTIVE),
                    SecurityIPBlock.expires_at > now,
                ),
                SecurityIPBlock.status == int(IPBlockStatus.RELEASED),
            )
        )

    result = await db.execute(stmt.order_by(desc(SecurityIPBlock.blocked_at)).limit(limit))
    items = [_serialize_ip_block(item) for item in result.scalars().all()]
    return {"items": items}


@security_management_router.post("/ip-blocks")
async def create_or_update_manual_ip_block(
    payload: ManualIPBlockUpsertRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: dict[str, Any] = Depends(verify_admin_session),
) -> dict[str, object]:
    """Create or update manual IP block entry."""
    _require_admin_write_role(admin_user)
    admin_user_id = int(admin_user["id"])
    try:
        row = await upsert_manual_ip_block(
            db,
            target=payload.target,
            severity_level=payload.severity_level,
            reason=payload.reason,
            is_permanent=payload.is_permanent,
            ttl_seconds=payload.ttl_seconds,
            request_path=request.url.path,
            request_method=request.method,
            commit=False,
        )
        await create_operation_log(
            db=db,
            admin_user_id=admin_user_id,
            operation_type=int(AdminOperationType.CREATE),
            resource_type="security_ip_block",
            resource_id=str(int(row.id)),
            resource_name=normalize_stored_network(str(row.target_network)).display_target,
            operation_desc="Manual IP block upsert",
            request=request,
            operation_meta={
                "target": payload.target,
                "target_type": _target_type_from_row(row),
                "severity_level": payload.severity_level,
                "is_permanent": payload.is_permanent,
                "ttl_seconds": payload.ttl_seconds,
            },
            commit=False,
        )
        await db.commit()
        await db.refresh(row)
        return {"item": _serialize_ip_block(row)}
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=_map_validation_error(str(exc))) from exc
    except HTTPException:
        await db.rollback()
        raise
    except Exception as exc:
        await db.rollback()
        logger.error("admin_upsert_manual_ip_block_failed", error=str(exc), exc_info=True)
        raise HTTPException(status_code=500, detail="系统错误") from exc


@security_management_router.post("/ip-blocks/{block_id}/release")
async def release_manual_ip_block(
    block_id: int,
    payload: ManualIPBlockReleaseRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: dict[str, Any] = Depends(verify_admin_session),
) -> dict[str, object]:
    """Release an active manual/automatic IP block."""
    _require_admin_write_role(admin_user)
    admin_user_id = int(admin_user["id"])
    try:
        row = await release_ip_block(
            db,
            block_id=block_id,
            release_reason=payload.release_reason,
            commit=False,
        )
        await create_operation_log(
            db=db,
            admin_user_id=admin_user_id,
            operation_type=int(AdminOperationType.UPDATE),
            resource_type="security_ip_block",
            resource_id=str(int(row.id)),
            resource_name=normalize_stored_network(str(row.target_network)).display_target,
            operation_desc="Manual IP block release",
            request=request,
            operation_meta={
                "release_reason": payload.release_reason.strip(),
            },
            commit=False,
        )
        await db.commit()
        await db.refresh(row)
        return {"item": _serialize_ip_block(row)}
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=_map_validation_error(str(exc))) from exc
    except HTTPException:
        await db.rollback()
        raise
    except Exception as exc:
        await db.rollback()
        logger.error("admin_release_manual_ip_block_failed", error=str(exc), exc_info=True)
        raise HTTPException(status_code=500, detail="系统错误") from exc
