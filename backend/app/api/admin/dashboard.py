"""
Admin Dashboard API endpoints.
Provides system statistics and monitoring data for admin panel.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any

from core.database import get_db
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
        # Simple direct query implementation instead of using manager
        from sqlalchemy import text

        # Get basic statistics
        stats = {
            "users": {"total": 0, "active": 0, "test_users": 0},
            "ai_characters": {"total": 0, "active": 0},
            "conversations": {"total": 0, "today": 0},
            "llm_requests": {"total": 0, "today": 0, "success_rate": 0.0},
        }

        # Count users
        result = await db.execute(text("SELECT COUNT(*) as total FROM users"))
        stats["users"]["total"] = result.scalar() or 0

        result = await db.execute(text("SELECT COUNT(*) as active FROM users WHERE status = 1"))
        stats["users"]["active"] = result.scalar() or 0

        result = await db.execute(text("SELECT COUNT(*) as test_users FROM users WHERE user_type = 3"))
        stats["users"]["test_users"] = result.scalar() or 0

        # Count AI characters
        result = await db.execute(text("SELECT COUNT(*) as total FROM ai_characters"))
        stats["ai_characters"]["total"] = result.scalar() or 0

        result = await db.execute(text("SELECT COUNT(*) as active FROM ai_characters WHERE status = 1"))
        stats["ai_characters"]["active"] = result.scalar() or 0

        # Count LLM requests
        result = await db.execute(text("SELECT COUNT(*) as total FROM llm_request_logs"))
        stats["llm_requests"]["total"] = result.scalar() or 0

        result = await db.execute(
            text("SELECT COUNT(*) as today FROM llm_request_logs WHERE DATE(created_at) = CURRENT_DATE")
        )
        stats["llm_requests"]["today"] = result.scalar() or 0

        # Calculate success rate (status: 1=pending, 2=success, 3=error)
        result = await db.execute(
            text(
                "SELECT COUNT(CASE WHEN status = 2 THEN 1 END)::float / COUNT(*)::float as success_rate "
                "FROM llm_request_logs WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'"
            )
        )
        success_rate = result.scalar()
        stats["llm_requests"]["success_rate"] = round(success_rate * 100, 2) if success_rate else 0.0

        return {"success": True, "data": stats, "message": "统计数据获取成功"}

    except Exception as e:
        logger.error("dashboard_stats_error", error=str(e))
        return {"success": False, "error": {"code": "DASHBOARD_STATS_ERROR", "message": "获取统计数据失败"}}
