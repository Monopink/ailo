from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Query, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from core.database import get_db
from models.admin import AdminOperationLog, AdminUser
from api.deps import get_current_admin_user
from schemas.admin.base import SuccessExtra
from utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/list", summary="Get operation logs")
async def get_operation_log_list(
    page: int = Query(1, description="Page number"),
    page_size: int = Query(10, description="Items per page"),
    admin_user_id: Optional[int] = Query(None, description="Admin user ID"),
    operation_type: Optional[str] = Query(None, description="Operation type"),
    resource_type: Optional[str] = Query(None, description="Resource type"),
    start_time: Optional[datetime] = Query(None, description="Start time"),
    end_time: Optional[datetime] = Query(None, description="End time"),
    current_admin: AdminUser = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get operation logs with pagination and filtering.
    """
    try:
        # Build query conditions
        conditions = []

        if admin_user_id:
            conditions.append(AdminOperationLog.admin_user_id == admin_user_id)
        if operation_type:
            conditions.append(AdminOperationLog.operation_type == operation_type)
        if resource_type:
            conditions.append(AdminOperationLog.resource_type == resource_type)
        if start_time:
            conditions.append(AdminOperationLog.created_at >= start_time)
        if end_time:
            conditions.append(AdminOperationLog.created_at <= end_time)

        # Get total count
        count_query = select(func.count(AdminOperationLog.id))
        if conditions:
            count_query = count_query.where(and_(*conditions))

        total_result = await db.execute(count_query)
        total = total_result.scalar()

        # Get paginated data
        query = (
            select(AdminOperationLog)
            .order_by(AdminOperationLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        if conditions:
            query = query.where(and_(*conditions))

        result = await db.execute(query)
        logs = result.scalars().all()

        # Convert to dict format
        data = []
        for log in logs:
            log_dict = {
                "id": log.id,
                "admin_user_id": log.admin_user_id,
                "operation_type": log.operation_type,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "resource_name": log.resource_name,
                "operation_desc": log.operation_desc,
                "ip_address": log.ip_address,
                "user_agent": log.user_agent,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            data.append(log_dict)

        return SuccessExtra(data=data, total=total, page=page, page_size=page_size)

    except Exception as e:
        logger.error("get_operation_log_list_error", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get operation logs")
