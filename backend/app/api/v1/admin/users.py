"""
Admin users API routes.
Simple user management with read-only operations.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from core.database import get_db
from models.admin import AdminUser
from api.deps import get_current_admin_user
from schemas.admin.base import SuccessExtra
from utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/list", summary="Get admin users list")
async def list_users(
    page: int = Query(1, description="Page number"),
    page_size: int = Query(20, description="Items per page"),
    current_admin: AdminUser = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get admin users list with pagination.
    Simple read-only operation for viewing admin users.
    """
    try:
        # Get total count
        count_result = await db.execute(select(func.count(AdminUser.id)))
        total = count_result.scalar()

        # Get paginated results
        offset = (page - 1) * page_size
        query = select(AdminUser).offset(offset).limit(page_size).order_by(AdminUser.created_at.desc())

        result = await db.execute(query)
        users = result.scalars().all()

        # Format response data
        data = []
        for user in users:
            user_data = {
                "id": user.id,
                "username": user.username,
                "role": user.role,
                "role_display": user.role_display,
                "is_active": user.status == 1,  # Convert status to boolean
                "last_login": user.last_login.strftime("%Y-%m-%d %H:%M:%S") if user.last_login else None,
                "login_count": user.login_count,
                "created_at": user.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            }
            data.append(user_data)

        return SuccessExtra(data=data, total=total, page=page, page_size=page_size)

    except Exception as e:
        logger.error("list_users_error", error=str(e), exc_info=True)
        return SuccessExtra(
            data=[], total=0, page=page, page_size=page_size, msg="Failed to get users list"
        )
