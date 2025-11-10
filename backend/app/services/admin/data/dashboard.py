"""Dashboard data service for admin panel."""

from typing import Dict, List, Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from utils.logging import get_logger

logger = get_logger(__name__)


async def get_total_users(db: AsyncSession) -> Dict[str, Any]:
    """
    Get total users count and growth rate.

    Returns:
        Dict with value, change percentage, and trend
    """
    try:
        # Total active users
        result = await db.execute(text("SELECT COUNT(*) FROM users WHERE status = 1"))
        total = result.scalar() or 0

        # New users this week
        result = await db.execute(
            text(
                """
                SELECT COUNT(*) FROM users
                WHERE created_at >= date_trunc('week', CURRENT_DATE)
                  AND status = 1
            """
            )
        )
        this_week = result.scalar() or 0

        # New users last week
        result = await db.execute(
            text(
                """
                SELECT COUNT(*) FROM users
                WHERE created_at >= date_trunc('week', CURRENT_DATE - INTERVAL '7 days')
                  AND created_at < date_trunc('week', CURRENT_DATE)
                  AND status = 1
            """
            )
        )
        last_week = result.scalar() or 0

        # Calculate change percentage
        if last_week > 0:
            change = ((this_week - last_week) / last_week) * 100
        else:
            change = 100.0 if this_week > 0 else 0.0

        trend = "up" if change > 0 else "down" if change < 0 else "stable"

        return {"value": total, "change": round(change, 1), "trend": trend}
    except Exception as e:
        logger.error("get_total_users_error", error=str(e), exc_info=True)
        return {"value": 0, "change": 0.0, "trend": "stable"}


async def get_ai_characters_stats(db: AsyncSession) -> Dict[str, Any]:
    """
    Get AI characters count and growth rate.

    Returns:
        Dict with value, change percentage, and trend
    """
    try:
        # Total active AI characters
        result = await db.execute(text("SELECT COUNT(*) FROM ai_characters WHERE status = 1"))
        total = result.scalar() or 0

        # New AI characters this week
        result = await db.execute(
            text(
                """
                SELECT COUNT(*) FROM ai_characters
                WHERE created_at >= date_trunc('week', CURRENT_DATE)
                  AND status = 1
            """
            )
        )
        this_week = result.scalar() or 0

        # New AI characters last week
        result = await db.execute(
            text(
                """
                SELECT COUNT(*) FROM ai_characters
                WHERE created_at >= date_trunc('week', CURRENT_DATE - INTERVAL '7 days')
                  AND created_at < date_trunc('week', CURRENT_DATE)
                  AND status = 1
            """
            )
        )
        last_week = result.scalar() or 0

        # Calculate change percentage
        if last_week > 0:
            change = ((this_week - last_week) / last_week) * 100
        else:
            change = 100.0 if this_week > 0 else 0.0

        trend = "up" if change > 0 else "down" if change < 0 else "stable"

        return {"value": total, "change": round(change, 1), "trend": trend}
    except Exception as e:
        logger.error("get_ai_characters_stats_error", error=str(e), exc_info=True)
        return {"value": 0, "change": 0.0, "trend": "stable"}


async def get_total_messages_stats(db: AsyncSession) -> Dict[str, Any]:
    """
    Get total messages count and growth rate.

    Returns:
        Dict with value, change percentage, and trend
    """
    try:
        # Total messages
        result = await db.execute(text("SELECT COUNT(*) FROM message_history"))
        total = result.scalar() or 0

        # Today's messages
        result = await db.execute(
            text(
                """
                SELECT COUNT(*) FROM message_history
                WHERE created_at >= CURRENT_DATE
            """
            )
        )
        today = result.scalar() or 0

        # Yesterday's messages
        result = await db.execute(
            text(
                """
                SELECT COUNT(*) FROM message_history
                WHERE created_at >= CURRENT_DATE - INTERVAL '1 day'
                  AND created_at < CURRENT_DATE
            """
            )
        )
        yesterday = result.scalar() or 0

        # Calculate change percentage
        if yesterday > 0:
            change = ((today - yesterday) / yesterday) * 100
        else:
            change = 100.0 if today > 0 else 0.0

        trend = "up" if change > 0 else "down" if change < 0 else "stable"

        return {"value": total, "change": round(change, 1), "trend": trend}
    except Exception as e:
        logger.error("get_total_messages_stats_error", error=str(e), exc_info=True)
        return {"value": 0, "change": 0.0, "trend": "stable"}


async def get_active_sessions_stats(db: AsyncSession) -> Dict[str, Any]:
    """
    Get active sessions count and growth rate.

    Returns:
        Dict with value, change percentage, and trend
    """
    try:
        # Current active sessions (not expired and active in last 30 minutes)
        result = await db.execute(
            text(
                """
                SELECT COUNT(*) FROM user_tokens
                WHERE status = 1
                  AND expires_at > NOW()
                  AND last_activity_at >= NOW() - INTERVAL '30 minutes'
            """
            )
        )
        current = result.scalar() or 0

        # Active sessions 1 hour ago
        result = await db.execute(
            text(
                """
                SELECT COUNT(*) FROM user_tokens
                WHERE status = 1
                  AND expires_at > NOW() - INTERVAL '1 hour'
                  AND last_activity_at >= NOW() - INTERVAL '90 minutes'
                  AND last_activity_at < NOW() - INTERVAL '60 minutes'
            """
            )
        )
        hour_ago = result.scalar() or 0

        # Calculate change percentage
        if hour_ago > 0:
            change = ((current - hour_ago) / hour_ago) * 100
        else:
            change = 100.0 if current > 0 else 0.0

        trend = "up" if change > 0 else "down" if change < 0 else "stable"

        return {"value": current, "change": round(change, 1), "trend": trend}
    except Exception as e:
        logger.error("get_active_sessions_stats_error", error=str(e), exc_info=True)
        return {"value": 0, "change": 0.0, "trend": "stable"}


async def get_user_growth_chart(db: AsyncSession) -> Dict[str, List]:
    """
    Get user growth data for last 7 days.

    Returns:
        Dict with labels and data arrays
    """
    try:
        result = await db.execute(
            text(
                """
                SELECT
                    DATE(created_at) as date,
                    COUNT(*) as new_users
                FROM users
                WHERE created_at >= CURRENT_DATE - INTERVAL '6 days'
                  AND status = 1
                GROUP BY DATE(created_at)
                ORDER BY date
            """
            )
        )
        rows = result.fetchall()

        # Create labels and data arrays
        labels = []
        data = []
        for row in rows:
            labels.append(row.date.strftime("%a"))  # Mon, Tue, etc.
            data.append(row.new_users)

        return {"labels": labels, "data": data}
    except Exception as e:
        logger.error("get_user_growth_chart_error", error=str(e), exc_info=True)
        return {"labels": [], "data": []}


async def get_message_volume_chart(db: AsyncSession) -> Dict[str, List]:
    """
    Get message volume data for last 7 days.

    Returns:
        Dict with labels and data arrays
    """
    try:
        result = await db.execute(
            text(
                """
                SELECT
                    DATE(created_at) as date,
                    COUNT(*) as message_count
                FROM message_history
                WHERE created_at >= CURRENT_DATE - INTERVAL '6 days'
                GROUP BY DATE(created_at)
                ORDER BY date
            """
            )
        )
        rows = result.fetchall()

        # Create labels and data arrays
        labels = []
        data = []
        for row in rows:
            labels.append(row.date.strftime("%a"))  # Mon, Tue, etc.
            data.append(row.message_count)

        return {"labels": labels, "data": data}
    except Exception as e:
        logger.error("get_message_volume_chart_error", error=str(e), exc_info=True)
        return {"labels": [], "data": []}


async def get_dashboard_stats(db: AsyncSession) -> Dict[str, Any]:
    """
    Get all dashboard statistics.

    Returns:
        Complete dashboard data including metrics and charts
    """
    try:
        # Get all metrics
        total_users = await get_total_users(db)
        ai_characters = await get_ai_characters_stats(db)
        total_messages = await get_total_messages_stats(db)
        active_sessions = await get_active_sessions_stats(db)

        # Get chart data
        user_growth = await get_user_growth_chart(db)
        message_volume = await get_message_volume_chart(db)

        return {
            "metrics": {
                "total_users": total_users,
                "ai_characters": ai_characters,
                "total_messages": total_messages,
                "active_sessions": active_sessions,
            },
            "charts": {"user_growth": user_growth, "message_volume": message_volume},
        }
    except Exception as e:
        logger.error("get_dashboard_stats_error", error=str(e), exc_info=True)
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
