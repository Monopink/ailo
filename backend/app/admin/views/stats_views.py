"""Statistics admin views.

This module contains Starlette-Admin views for statistics tables.
All views are read-only.
"""

# Import statistics models
from starlette.requests import Request
from starlette_admin import DateField, IntegerField, StringField
from starlette_admin.contrib.sqla import ModelView

from app.models.system.stats import (
    StatsAIDaily,
    StatsAIMonthly,
    StatsAIWeekly,
    StatsMessageDaily,
    StatsMessageMonthly,
    StatsMessageWeekly,
    StatsUserDaily,
    StatsUserMonthly,
    StatsUserWeekly,
)


class StatsUserDailyView(ModelView):
    """User statistics - daily view."""

    label = "User Daily"
    name = "User Daily"

    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    fields_default_sort = [("stat_date", True)]
    searchable_fields = ["stat_date"]
    sortable_fields = ["id", "stat_date", "new_users", "active_users", "total_users"]

    fields = [
        StringField("id", label="ID", help_text="Unique ID"),
        DateField("stat_date", label="Date", help_text="Statistics date"),
        IntegerField("total_users", label="Total Users", help_text="Total users count"),
        IntegerField("new_users", label="New Users", help_text="New users count"),
        IntegerField("active_users", label="Active Users", help_text="Active users count"),
        IntegerField("subscriptions", label="Subscriptions", help_text="Total subscriptions"),
        IntegerField("new_subscriptions", label="New Subscriptions", help_text="New subscriptions"),
        IntegerField(
            "canceled_subscriptions",
            label="Canceled Subscriptions",
            help_text="Canceled subscriptions",
        ),
        "created_at",
    ]


class StatsUserWeeklyView(ModelView):
    """User statistics - weekly view."""

    label = "User Weekly"
    name = "User Weekly"

    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    fields_default_sort = [("stat_date", True)]
    searchable_fields = ["stat_date"]
    sortable_fields = ["id", "stat_date", "new_users", "active_users", "total_users"]

    fields = [
        StringField("id", label="ID", help_text="Unique ID"),
        DateField("stat_date", label="Week Start", help_text="Week start date"),
        IntegerField("total_users", label="Total Users", help_text="Total users count"),
        IntegerField("new_users", label="New Users", help_text="New users count"),
        IntegerField("active_users", label="Active Users", help_text="Active users count"),
        IntegerField("subscriptions", label="Subscriptions", help_text="Total subscriptions"),
        IntegerField("new_subscriptions", label="New Subscriptions", help_text="New subscriptions"),
        IntegerField(
            "canceled_subscriptions",
            label="Canceled Subscriptions",
            help_text="Canceled subscriptions",
        ),
        "created_at",
    ]


class StatsUserMonthlyView(ModelView):
    """User statistics - monthly view."""

    label = "User Monthly"
    name = "User Monthly"

    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    fields_default_sort = [("stat_date", True)]
    searchable_fields = ["stat_date"]
    sortable_fields = ["id", "stat_date", "new_users", "active_users", "total_users"]

    fields = [
        StringField("id", label="ID", help_text="Unique ID"),
        DateField("stat_date", label="Month Start", help_text="Month start date"),
        IntegerField("total_users", label="Total Users", help_text="Total users count"),
        IntegerField("new_users", label="New Users", help_text="New users count"),
        IntegerField("active_users", label="Active Users", help_text="Active users count"),
        IntegerField("subscriptions", label="Subscriptions", help_text="Total subscriptions"),
        IntegerField("new_subscriptions", label="New Subscriptions", help_text="New subscriptions"),
        IntegerField(
            "canceled_subscriptions",
            label="Canceled Subscriptions",
            help_text="Canceled subscriptions",
        ),
        "created_at",
    ]


class StatsMessageDailyView(ModelView):
    """Message statistics - daily view."""

    label = "Message Daily"
    name = "Message Daily"

    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    fields_default_sort = [("stat_date", True)]
    searchable_fields = ["stat_date"]
    sortable_fields = [
        "id",
        "stat_date",
        "total_messages",
        "avg_messages_per_user",
        "active_conversations",
    ]

    fields = [
        StringField("id", label="ID", help_text="Unique ID"),
        DateField("stat_date", label="Date", help_text="Statistics date"),
        IntegerField("total_messages", label="Total Messages", help_text="Total messages count"),
        "avg_messages_per_user",
        IntegerField(
            "active_conversations",
            label="Active Conversations",
            help_text="Active conversations count",
        ),
        "created_at",
    ]


class StatsMessageWeeklyView(ModelView):
    """Message statistics - weekly view."""

    label = "Message Weekly"
    name = "Message Weekly"

    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    fields_default_sort = [("stat_date", True)]
    searchable_fields = ["stat_date"]
    sortable_fields = [
        "id",
        "stat_date",
        "total_messages",
        "avg_messages_per_user",
        "active_conversations",
    ]

    fields = [
        StringField("id", label="ID", help_text="Unique ID"),
        DateField("stat_date", label="Week Start", help_text="Week start date"),
        IntegerField("total_messages", label="Total Messages", help_text="Total messages count"),
        "avg_messages_per_user",
        IntegerField(
            "active_conversations",
            label="Active Conversations",
            help_text="Active conversations count",
        ),
        "created_at",
    ]


class StatsMessageMonthlyView(ModelView):
    """Message statistics - monthly view."""

    label = "Message Monthly"
    name = "Message Monthly"

    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    fields_default_sort = [("stat_date", True)]
    searchable_fields = ["stat_date"]
    sortable_fields = [
        "id",
        "stat_date",
        "total_messages",
        "avg_messages_per_user",
        "active_conversations",
    ]

    fields = [
        StringField("id", label="ID", help_text="Unique ID"),
        DateField("stat_date", label="Month Start", help_text="Month start date"),
        IntegerField("total_messages", label="Total Messages", help_text="Total messages count"),
        "avg_messages_per_user",
        IntegerField(
            "active_conversations",
            label="Active Conversations",
            help_text="Active conversations count",
        ),
        "created_at",
    ]


class StatsAIDailyView(ModelView):
    """AI statistics - daily view."""

    label = "AI Daily"
    name = "AI Daily"

    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    fields_default_sort = [("stat_date", True)]
    searchable_fields = ["stat_date"]
    sortable_fields = [
        "id",
        "stat_date",
        "ai_instances",
        "active_ai_instances",
        "ai_requests_count",
    ]

    fields = [
        StringField("id", label="ID", help_text="Unique ID"),
        DateField("stat_date", label="Date", help_text="Statistics date"),
        IntegerField("ai_instances", label="AI Instances", help_text="Total AI instance count"),
        IntegerField(
            "active_ai_instances", label="Active AI Instances", help_text="Active AI instance count"
        ),
        IntegerField("ai_requests_count", label="AI Requests", help_text="AI request count"),
        "avg_ai_requests_per_user",
        "created_at",
    ]


class StatsAIWeeklyView(ModelView):
    """AI statistics - weekly view."""

    label = "AI Weekly"
    name = "AI Weekly"

    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    fields_default_sort = [("stat_date", True)]
    searchable_fields = ["stat_date"]
    sortable_fields = [
        "id",
        "stat_date",
        "ai_instances",
        "active_ai_instances",
        "ai_requests_count",
    ]

    fields = [
        StringField("id", label="ID", help_text="Unique ID"),
        DateField("stat_date", label="Week Start", help_text="Week start date"),
        IntegerField("ai_instances", label="AI Instances", help_text="Total AI instance count"),
        IntegerField(
            "active_ai_instances", label="Active AI Instances", help_text="Active AI instance count"
        ),
        IntegerField("ai_requests_count", label="AI Requests", help_text="AI request count"),
        "avg_ai_requests_per_user",
        "created_at",
    ]


class StatsAIMonthlyView(ModelView):
    """AI statistics - monthly view."""

    label = "AI Monthly"
    name = "AI Monthly"

    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    fields_default_sort = [("stat_date", True)]
    searchable_fields = ["stat_date"]
    sortable_fields = [
        "id",
        "stat_date",
        "ai_instances",
        "active_ai_instances",
        "ai_requests_count",
    ]

    fields = [
        StringField("id", label="ID", help_text="Unique ID"),
        DateField("stat_date", label="Month Start", help_text="Month start date"),
        IntegerField("ai_instances", label="AI Instances", help_text="Total AI instance count"),
        IntegerField(
            "active_ai_instances", label="Active AI Instances", help_text="Active AI instance count"
        ),
        IntegerField("ai_requests_count", label="AI Requests", help_text="AI request count"),
        "avg_ai_requests_per_user",
        "created_at",
    ]


# Create view instances
stats_user_daily_view = StatsUserDailyView(
    StatsUserDaily, name="User Daily", icon="fa fa-calendar-day", identity="stats_user_daily"
)
stats_user_weekly_view = StatsUserWeeklyView(
    StatsUserWeekly, name="User Weekly", icon="fa fa-calendar-week", identity="stats_user_weekly"
)
stats_user_monthly_view = StatsUserMonthlyView(
    StatsUserMonthly, name="User Monthly", icon="fa fa-calendar-alt", identity="stats_user_monthly"
)

stats_message_daily_view = StatsMessageDailyView(
    StatsMessageDaily,
    name="Message Daily",
    icon="fa fa-calendar-day",
    identity="stats_message_daily",
)
stats_message_weekly_view = StatsMessageWeeklyView(
    StatsMessageWeekly,
    name="Message Weekly",
    icon="fa fa-calendar-week",
    identity="stats_message_weekly",
)
stats_message_monthly_view = StatsMessageMonthlyView(
    StatsMessageMonthly,
    name="Message Monthly",
    icon="fa fa-calendar-alt",
    identity="stats_message_monthly",
)

stats_ai_daily_view = StatsAIDailyView(
    StatsAIDaily, name="AI Daily", icon="fa fa-calendar-day", identity="stats_ai_daily"
)
stats_ai_weekly_view = StatsAIWeeklyView(
    StatsAIWeekly, name="AI Weekly", icon="fa fa-calendar-week", identity="stats_ai_weekly"
)
stats_ai_monthly_view = StatsAIMonthlyView(
    StatsAIMonthly, name="AI Monthly", icon="fa fa-calendar-alt", identity="stats_ai_monthly"
)

# Export all statistics views
STATS_MODEL_VIEWS = [
    stats_user_daily_view,
    stats_user_weekly_view,
    stats_user_monthly_view,
    stats_message_daily_view,
    stats_message_weekly_view,
    stats_message_monthly_view,
    stats_ai_daily_view,
    stats_ai_weekly_view,
    stats_ai_monthly_view,
]
