"""
Admin Dashboard API endpoints.
Provides system statistics and monitoring data for admin panel.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any

from core.database import get_db
from services.admin.dashboard_service import get_dashboard_stats
from utils.logging import get_logger

logger = get_logger(__name__)

dashboard_router = APIRouter()


@dashboard_router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """
    Get dashboard statistics data.

    Returns:
        Dashboard statistics including metrics, charts, and system status
    """
    try:
        stats = await get_dashboard_stats(db)
        return stats
    except Exception as e:
        logger.error("dashboard_stats_error", error=str(e), exc_info=True)
        # Return empty data structure on error
        return {
            "metrics": {
                "total_users": {"value": 0, "change": 0.0, "trend": "stable"},
                "ai_characters": {"value": 0, "change": 0.0, "trend": "stable"},
                "total_messages": {"value": 0, "change": 0.0, "trend": "stable"},
                "active_sessions": {"value": 0, "change": 0.0, "trend": "stable"},
            },
            "charts": {
                "user_growth": {"labels": [], "data": []},
                "message_volume": {"labels": [], "data": []},
            },
        }
