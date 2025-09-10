"""
Admin Dashboard API endpoints.
Provides system statistics and monitoring data for admin panel.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any

from core.database import get_db
from services.admin.managers.dashboard_manager import DashboardManager
from services.admin.utils.response_formatter import (
    format_success_response,
    format_error_response,
)
from utils.logging import get_logger

logger = get_logger(__name__)

dashboard_router = APIRouter()


@dashboard_router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """
    Get dashboard statistics data.

    Returns:
        Dashboard statistics including user counts, message counts, etc.
    """
    try:
        manager = DashboardManager(db)
        stats = await manager.get_system_statistics()

        return format_success_response(stats, "统计数据获取成功")

    except Exception as e:
        logger.error("dashboard_stats_error", error=str(e))
        return format_error_response("DASHBOARD_STATS_ERROR", "获取统计数据失败")
