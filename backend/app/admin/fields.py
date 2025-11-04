"""
Custom fields for Starlette-Admin with timezone support.
"""

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from starlette.requests import Request
from starlette_admin.fields import DateTimeField
from starlette_admin._types import RequestAction


class LocalDateTimeField(DateTimeField):
    """
    DateTimeField that displays datetime in user's local timezone.

    Only converts timezone for display (LIST/DETAIL views).
    EDIT views use default behavior.
    """

    async def serialize_value(self, request: Request, value: Any, action: RequestAction) -> str:
        """Convert UTC datetime to user's timezone for display."""
        if value is None or not isinstance(value, datetime):
            return await super().serialize_value(request, value, action)

        # Only convert for LIST/DETAIL display, not for EDIT forms
        if action == RequestAction.EDIT:
            return await super().serialize_value(request, value, action)

        user_tz_str = request.cookies.get("timezone")
        if not user_tz_str:
            return await super().serialize_value(request, value, action)

        try:
            user_tz = ZoneInfo(user_tz_str)
            local_dt = value.astimezone(user_tz)
            return local_dt.strftime(self.output_format or "%Y-%m-%d %H:%M:%S")
        except Exception:
            return await super().serialize_value(request, value, action)
