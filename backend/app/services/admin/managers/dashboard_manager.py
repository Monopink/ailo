"""
Dashboard Manager.
Manages dashboard data aggregation and system statistics.
"""

from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text

from models.user import User
from models.ai.character import AICharacter
from models.ai.log import AIRequestLog
from utils.logging import get_logger

logger = get_logger(__name__)


class DashboardManager:
    """
    Manages dashboard data aggregation and system statistics.

    Handles complex data queries and aggregations for admin dashboard.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize dashboard manager.

        Args:
            db: Database session
        """
        self.db = db

    async def get_system_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive system statistics for dashboard.

        Returns:
            System statistics including user counts, message counts, etc.

        Raises:
            Exception: If statistics collection fails
        """
        try:
            # Get basic counts
            stats = {}

            # Total users count
            user_count_result = await self.db.execute(select(func.count(User.id)).where(User.status == 1))
            stats["total_users"] = user_count_result.scalar() or 0

            # Total AI characters count
            character_count_result = await self.db.execute(
                select(func.count(AICharacter.id)).where(AICharacter.status == 1)
            )
            stats["total_ai_characters"] = character_count_result.scalar() or 0

            # Total messages count (from AI request logs)
            message_count_result = await self.db.execute(select(func.count(AIRequestLog.id)))
            stats["total_messages"] = message_count_result.scalar() or 0

            # Active sessions (placeholder - would need session tracking)
            stats["active_sessions"] = 0  # TODO: Implement session tracking

            # Today's statistics
            today_stats = await self._get_today_statistics()
            stats.update(today_stats)

            # System status
            stats["system_status"] = await self._get_system_status()

            logger.info(
                "dashboard_statistics_collected",
                total_users=stats["total_users"],
                total_characters=stats["total_ai_characters"],
                total_messages=stats["total_messages"],
            )

            return stats

        except Exception as e:
            logger.error(
                "dashboard_statistics_failed",
                error=str(e),
                exc_info=True,
            )
            raise

    async def _get_today_statistics(self) -> Dict[str, Any]:
        """
        Get today's statistics.

        Returns:
            Today's statistics
        """
        try:
            # Today's new users
            today_users_result = await self.db.execute(
                text(
                    """
                    SELECT COUNT(*) 
                    FROM users 
                    WHERE DATE(created_at) = CURRENT_DATE
                    AND status = 1
                """
                )
            )
            today_new_users = today_users_result.scalar() or 0

            # Today's messages
            today_messages_result = await self.db.execute(
                text(
                    """
                    SELECT COUNT(*) 
                    FROM ai_request_logs 
                    WHERE DATE(created_at) = CURRENT_DATE
                """
                )
            )
            today_messages = today_messages_result.scalar() or 0

            return {
                "today_new_users": today_new_users,
                "today_messages": today_messages,
            }

        except Exception as e:
            logger.warning(
                "today_statistics_failed",
                error=str(e),
            )
            return {
                "today_new_users": 0,
                "today_messages": 0,
            }

    async def _get_system_status(self) -> str:
        """
        Get system health status.

        Returns:
            System status string
        """
        try:
            # Check database connectivity
            await self.db.execute(text("SELECT 1"))

            # TODO: Add more health checks
            # - LLM service availability
            # - External service connectivity
            # - Resource usage monitoring

            return "healthy"

        except Exception as e:
            logger.warning(
                "system_status_check_failed",
                error=str(e),
            )
            return "degraded"

    async def get_user_statistics(self) -> Dict[str, Any]:
        """
        Get detailed user statistics.

        Returns:
            User statistics breakdown
        """
        try:
            # User status breakdown
            user_status_result = await self.db.execute(
                select(User.status, func.count(User.id)).group_by(User.status)
            )
            user_status_breakdown = {row[0]: row[1] for row in user_status_result.fetchall()}

            # User type breakdown
            user_type_result = await self.db.execute(
                select(User.user_type, func.count(User.id)).group_by(User.user_type)
            )
            user_type_breakdown = {row[0]: row[1] for row in user_type_result.fetchall()}

            return {
                "status_breakdown": user_status_breakdown,
                "type_breakdown": user_type_breakdown,
            }

        except Exception as e:
            logger.error(
                "user_statistics_failed",
                error=str(e),
                exc_info=True,
            )
            return {
                "status_breakdown": {},
                "type_breakdown": {},
            }

    async def get_ai_statistics(self) -> Dict[str, Any]:
        """
        Get detailed AI character statistics.

        Returns:
            AI character statistics breakdown
        """
        try:
            # Character status breakdown
            character_status_result = await self.db.execute(
                select(AICharacter.status, func.count(AICharacter.id)).group_by(AICharacter.status)
            )
            character_status_breakdown = {row[0]: row[1] for row in character_status_result.fetchall()}

            # Character creator breakdown
            character_creator_result = await self.db.execute(
                select(AICharacter.creator, func.count(AICharacter.id)).group_by(AICharacter.creator)
            )
            character_creator_breakdown = {row[0]: row[1] for row in character_creator_result.fetchall()}

            return {
                "status_breakdown": character_status_breakdown,
                "creator_breakdown": character_creator_breakdown,
            }

        except Exception as e:
            logger.error(
                "ai_statistics_failed",
                error=str(e),
                exc_info=True,
            )
            return {
                "status_breakdown": {},
                "creator_breakdown": {},
            }

    async def get_message_statistics(self) -> Dict[str, Any]:
        """
        Get detailed message statistics.

        Returns:
            Message statistics breakdown
        """
        try:
            # Request status breakdown
            request_status_result = await self.db.execute(
                select(AIRequestLog.status, func.count(AIRequestLog.id)).group_by(AIRequestLog.status)
            )
            request_status_breakdown = {row[0]: row[1] for row in request_status_result.fetchall()}

            # Average response time
            avg_response_time_result = await self.db.execute(
                select(func.avg(AIRequestLog.response_time_ms)).where(AIRequestLog.status == "success")
            )
            avg_response_time = avg_response_time_result.scalar() or 0

            return {
                "status_breakdown": request_status_breakdown,
                "avg_response_time_ms": round(float(avg_response_time), 2),
            }

        except Exception as e:
            logger.error(
                "message_statistics_failed",
                error=str(e),
                exc_info=True,
            )
            return {
                "status_breakdown": {},
                "avg_response_time_ms": 0,
            }
