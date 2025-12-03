"""
AI Request Log CRUD operations.

This module provides both standard CRUD operations and complex queries
for AI request logging and analytics.
"""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.ai import AIRequestLog
from app.schemas.ai import AIRequestLogCreate, AIRequestLogUpdate
from app.utils.logging import get_logger

logger = get_logger(__name__)


class CRUDAIRequestLog(CRUDBase[AIRequestLog, AIRequestLogCreate, AIRequestLogUpdate]):
    """AI Request Log CRUD operations with complex queries."""

    async def get_usage_stats(
        self, db: AsyncSession, *, instance_id: int | None = None, days: int = 7
    ) -> dict[str, Any]:
        """
        Get usage statistics for AI requests.

        Args:
            db: Database session
            instance_id: Instance ID (optional, for specific instance stats)
            days: Number of days to look back

        Returns:
            Dictionary containing usage statistics
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)

            # Build base query
            query = select(
                func.count(AIRequestLog.id).label("total_requests"),
                func.count(AIRequestLog.id)
                .filter(AIRequestLog.status == 1)
                .label("successful_requests"),
                func.count(AIRequestLog.id)
                .filter(AIRequestLog.status == 2)
                .label("failed_requests"),
                func.avg(AIRequestLog.response_time).label("avg_response_time"),
                func.sum(AIRequestLog.token_count).label("total_tokens"),
            ).where(AIRequestLog.created_at >= cutoff_date)

            if instance_id:
                query = query.where(AIRequestLog.instance_id == instance_id)

            result = await db.execute(query)
            row = result.first()
            if row:
                total_requests = row.total_requests or 0
                successful_requests = row.successful_requests or 0
                failed_requests = row.failed_requests or 0
                avg_response_time = float(row.avg_response_time or 0)
                total_tokens = row.total_tokens or 0
            else:
                total_requests = successful_requests = failed_requests = total_tokens = 0
                avg_response_time = 0.0

            stats = {
                "total_requests": total_requests,
                "successful_requests": successful_requests,
                "failed_requests": failed_requests,
                "success_rate": (
                    (successful_requests / total_requests * 100) if total_requests else 0
                ),
                "avg_response_time": avg_response_time,
                "total_tokens": total_tokens,
                "period_days": days,
            }

            logger.debug(
                "usage_stats_retrieved",
                instance_id=instance_id,
                days=days,
                total_requests=stats["total_requests"],
            )

            return stats

        except Exception as e:
            logger.error(
                "usage_stats_query_failed", error=str(e), instance_id=instance_id, days=days
            )
            # Return empty stats on error
            return {
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "success_rate": 0,
                "avg_response_time": 0,
                "total_tokens": 0,
                "period_days": days,
            }

    async def get_error_logs(
        self, db: AsyncSession, *, instance_id: int | None = None, limit: int = 50
    ) -> list[AIRequestLog]:
        """
        Get recent error logs.

        Args:
            db: Database session
            instance_id: Instance ID (optional, for specific instance errors)
            limit: Maximum number of error logs to return

        Returns:
            List of error log entries
        """
        try:
            query = select(AIRequestLog).where(AIRequestLog.status == 2)  # failed status

            if instance_id:
                query = query.where(AIRequestLog.instance_id == instance_id)

            query = query.order_by(desc(AIRequestLog.created_at)).limit(limit)

            result = await db.execute(query)
            error_logs = list(result.scalars().all())

            logger.debug("error_logs_retrieved", instance_id=instance_id, count=len(error_logs))

            return error_logs

        except Exception as e:
            logger.error("error_logs_query_failed", error=str(e), instance_id=instance_id)
            # Non-fatal error: return empty list
            return []

    async def get_instance_logs(
        self, db: AsyncSession, *, instance_id: int, skip: int = 0, limit: int = 100
    ) -> list[AIRequestLog]:
        """
        Get request logs for a specific instance.

        Args:
            db: Database session
            instance_id: Instance ID
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of request logs
        """
        try:
            result = await db.execute(
                select(AIRequestLog)
                .where(AIRequestLog.instance_id == instance_id)
                .order_by(desc(AIRequestLog.created_at))
                .offset(skip)
                .limit(limit)
            )

            logs = list(result.scalars().all())

            logger.debug("instance_logs_retrieved", instance_id=instance_id, count=len(logs))

            return logs

        except Exception as e:
            logger.error("instance_logs_query_failed", error=str(e), instance_id=instance_id)
            # Non-fatal error: return empty list
            return []

    async def get_user_logs(
        self, db: AsyncSession, *, user_qiao_id: str, skip: int = 0, limit: int = 100
    ) -> list[AIRequestLog]:
        """
        Get request logs for a specific user.

        Args:
            db: Database session
            user_qiao_id: User's qiao_id
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of request logs
        """
        try:
            result = await db.execute(
                select(AIRequestLog)
                .where(AIRequestLog.user_qiao_id == user_qiao_id)
                .order_by(desc(AIRequestLog.created_at))
                .offset(skip)
                .limit(limit)
            )

            logs = list(result.scalars().all())

            logger.debug("user_logs_retrieved", user_qiao_id=user_qiao_id, count=len(logs))

            return logs

        except Exception as e:
            logger.error("user_logs_query_failed", error=str(e), user_qiao_id=user_qiao_id)
            # Non-fatal error: return empty list
            return []

    async def get_daily_stats(
        self, db: AsyncSession, *, instance_id: int | None = None, days: int = 30
    ) -> list[dict[str, Any]]:
        """
        Get daily usage statistics.

        Args:
            db: Database session
            instance_id: Instance ID (optional, for specific instance stats)
            days: Number of days to look back

        Returns:
            List of daily statistics
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)

            # Build query for daily stats
            query = select(
                func.date(AIRequestLog.created_at).label("date"),
                func.count(AIRequestLog.id).label("total_requests"),
                func.count(AIRequestLog.id)
                .filter(AIRequestLog.status == 1)
                .label("successful_requests"),
                func.avg(AIRequestLog.response_time).label("avg_response_time"),
                func.sum(AIRequestLog.token_count).label("total_tokens"),
            ).where(AIRequestLog.created_at >= cutoff_date)

            if instance_id:
                query = query.where(AIRequestLog.instance_id == instance_id)

            query = query.group_by(func.date(AIRequestLog.created_at)).order_by(
                func.date(AIRequestLog.created_at)
            )

            result = await db.execute(query)
            rows = result.all()

            daily_stats = []
            for row in rows:
                daily_stats.append(
                    {
                        "date": row.date.isoformat(),
                        "total_requests": row.total_requests,
                        "successful_requests": row.successful_requests,
                        "success_rate": (
                            (row.successful_requests / row.total_requests * 100)
                            if row.total_requests
                            else 0
                        ),
                        "avg_response_time": float(row.avg_response_time or 0),
                        "total_tokens": row.total_tokens or 0,
                    }
                )

            logger.debug(
                "daily_stats_retrieved",
                instance_id=instance_id,
                days=days,
                records=len(daily_stats),
            )

            return daily_stats

        except Exception as e:
            logger.error(
                "daily_stats_query_failed", error=str(e), instance_id=instance_id, days=days
            )
            # Non-fatal error: return empty list
            return []

    async def cleanup_old_logs(self, db: AsyncSession, *, days_to_keep: int = 90) -> int:
        """
        Clean up old request logs.

        Args:
            db: Database session
            days_to_keep: Number of days of logs to keep

        Returns:
            Number of logs deleted
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)

            # Get logs to delete
            result = await db.execute(
                select(AIRequestLog).where(AIRequestLog.created_at < cutoff_date)
            )

            logs_to_delete = result.scalars().all()
            deleted_count = len(logs_to_delete)

            # Delete logs
            for log in logs_to_delete:
                await db.delete(log)

            await db.flush()

            logger.info(
                "old_logs_cleaned_up", days_to_keep=days_to_keep, deleted_count=deleted_count
            )

            return deleted_count

        except Exception as e:
            logger.error("log_cleanup_failed", error=str(e), days_to_keep=days_to_keep)
            return 0


ai_request_log = CRUDAIRequestLog(AIRequestLog)
