"""
System statistics related models.

This module contains SQLAlchemy models for various system statistics.
"""

from datetime import date
from sqlalchemy import Date, Integer, DECIMAL, Index
from sqlalchemy.orm import Mapped, mapped_column

from models.base import AutoIncrementModel


# User Statistics Tables


class StatsUserDaily(AutoIncrementModel):
    """Daily user statistics model."""

    __tablename__ = "stats_user_daily"

    stat_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True, comment="Statistics date")

    total_users: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="Total user count")

    new_users: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="New user count")

    active_users: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Active user count"
    )

    subscriptions: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Total subscription count"
    )

    new_subscriptions: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="New subscription count"
    )

    canceled_subscriptions: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Canceled subscription count"
    )

    # Indexes
    __table_args__ = (Index("idx_stats_user_daily_stat_date", "stat_date"),)


class StatsUserWeekly(AutoIncrementModel):
    """Weekly user statistics model."""

    __tablename__ = "stats_user_weekly"

    stat_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True, comment="Week start date")

    total_users: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="Total user count")

    new_users: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="New user count")

    active_users: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Active user count"
    )

    subscriptions: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Total subscription count"
    )

    new_subscriptions: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="New subscription count"
    )

    canceled_subscriptions: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Canceled subscription count"
    )

    # Indexes
    __table_args__ = (Index("idx_stats_user_weekly_stat_date", "stat_date"),)


class StatsUserMonthly(AutoIncrementModel):
    """Monthly user statistics model."""

    __tablename__ = "stats_user_monthly"

    stat_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True, comment="Month start date")

    total_users: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="Total user count")

    new_users: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="New user count")

    active_users: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Active user count"
    )

    subscriptions: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Total subscription count"
    )

    new_subscriptions: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="New subscription count"
    )

    canceled_subscriptions: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Canceled subscription count"
    )

    # Indexes
    __table_args__ = (Index("idx_stats_user_monthly_stat_date", "stat_date"),)


# Revenue Statistics Tables


class StatsRevenueDaily(AutoIncrementModel):
    """Daily revenue statistics model."""

    __tablename__ = "stats_revenue_daily"

    stat_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True, comment="Statistics date")

    total_revenue: Mapped[float] = mapped_column(
        DECIMAL(15, 2), nullable=False, default=0.00, comment="Total revenue"
    )

    orders_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="Order count")

    avg_order_amount: Mapped[float] = mapped_column(
        DECIMAL(10, 2), nullable=False, default=0.00, comment="Average order amount"
    )

    refund_amount: Mapped[float] = mapped_column(
        DECIMAL(15, 2), nullable=False, default=0.00, comment="Refund amount"
    )

    # Indexes
    __table_args__ = (Index("idx_stats_revenue_daily_stat_date", "stat_date"),)


class StatsRevenueWeekly(AutoIncrementModel):
    """Weekly revenue statistics model."""

    __tablename__ = "stats_revenue_weekly"

    stat_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True, comment="Week start date")

    total_revenue: Mapped[float] = mapped_column(
        DECIMAL(15, 2), nullable=False, default=0.00, comment="Total revenue"
    )

    orders_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="Order count")

    avg_order_amount: Mapped[float] = mapped_column(
        DECIMAL(10, 2), nullable=False, default=0.00, comment="Average order amount"
    )

    refund_amount: Mapped[float] = mapped_column(
        DECIMAL(15, 2), nullable=False, default=0.00, comment="Refund amount"
    )

    # Indexes
    __table_args__ = (Index("idx_stats_revenue_weekly_stat_date", "stat_date"),)


class StatsRevenueMonthly(AutoIncrementModel):
    """Monthly revenue statistics model."""

    __tablename__ = "stats_revenue_monthly"

    stat_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True, comment="Month start date")

    total_revenue: Mapped[float] = mapped_column(
        DECIMAL(15, 2), nullable=False, default=0.00, comment="Total revenue"
    )

    orders_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="Order count")

    avg_order_amount: Mapped[float] = mapped_column(
        DECIMAL(10, 2), nullable=False, default=0.00, comment="Average order amount"
    )

    refund_amount: Mapped[float] = mapped_column(
        DECIMAL(15, 2), nullable=False, default=0.00, comment="Refund amount"
    )

    # Indexes
    __table_args__ = (Index("idx_stats_revenue_monthly_stat_date", "stat_date"),)


# Message Statistics Tables


class StatsMessageDaily(AutoIncrementModel):
    """Daily message statistics model."""

    __tablename__ = "stats_message_daily"

    stat_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True, comment="Statistics date")

    total_messages: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Total message count"
    )

    avg_messages_per_user: Mapped[float] = mapped_column(
        DECIMAL(10, 2), nullable=False, default=0.00, comment="Average messages per user"
    )

    active_conversations: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Active conversation count"
    )

    # Indexes
    __table_args__ = (Index("idx_stats_message_daily_stat_date", "stat_date"),)


class StatsMessageWeekly(AutoIncrementModel):
    """Weekly message statistics model."""

    __tablename__ = "stats_message_weekly"

    stat_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True, comment="Week start date")

    total_messages: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Total message count"
    )

    avg_messages_per_user: Mapped[float] = mapped_column(
        DECIMAL(10, 2), nullable=False, default=0.00, comment="Average messages per user"
    )

    active_conversations: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Active conversation count"
    )

    # Indexes
    __table_args__ = (Index("idx_stats_message_weekly_stat_date", "stat_date"),)


class StatsMessageMonthly(AutoIncrementModel):
    """Monthly message statistics model."""

    __tablename__ = "stats_message_monthly"

    stat_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True, comment="Month start date")

    total_messages: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Total message count"
    )

    avg_messages_per_user: Mapped[float] = mapped_column(
        DECIMAL(10, 2), nullable=False, default=0.00, comment="Average messages per user"
    )

    active_conversations: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Active conversation count"
    )

    # Indexes
    __table_args__ = (Index("idx_stats_message_monthly_stat_date", "stat_date"),)


# AI Statistics Tables


class StatsAIDaily(AutoIncrementModel):
    """Daily AI statistics model."""

    __tablename__ = "stats_ai_daily"

    stat_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True, comment="Statistics date")

    ai_characters: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Total AI character count"
    )

    active_ai_characters: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Active AI character count"
    )

    ai_requests_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="AI request count"
    )

    avg_ai_requests_per_user: Mapped[float] = mapped_column(
        DECIMAL(10, 2), nullable=False, default=0.00, comment="Average AI requests per user"
    )

    # Indexes
    __table_args__ = (Index("idx_stats_ai_daily_stat_date", "stat_date"),)


class StatsAIWeekly(AutoIncrementModel):
    """Weekly AI statistics model."""

    __tablename__ = "stats_ai_weekly"

    stat_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True, comment="Week start date")

    ai_characters: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Total AI character count"
    )

    active_ai_characters: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Active AI character count"
    )

    ai_requests_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="AI request count"
    )

    avg_ai_requests_per_user: Mapped[float] = mapped_column(
        DECIMAL(10, 2), nullable=False, default=0.00, comment="Average AI requests per user"
    )

    # Indexes
    __table_args__ = (Index("idx_stats_ai_weekly_stat_date", "stat_date"),)


class StatsAIMonthly(AutoIncrementModel):
    """Monthly AI statistics model."""

    __tablename__ = "stats_ai_monthly"

    stat_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True, comment="Month start date")

    ai_characters: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Total AI character count"
    )

    active_ai_characters: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Active AI character count"
    )

    ai_requests_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="AI request count"
    )

    avg_ai_requests_per_user: Mapped[float] = mapped_column(
        DECIMAL(10, 2), nullable=False, default=0.00, comment="Average AI requests per user"
    )

    # Indexes
    __table_args__ = (Index("idx_stats_ai_monthly_stat_date", "stat_date"),)
