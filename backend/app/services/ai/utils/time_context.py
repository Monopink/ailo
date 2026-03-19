"""Time context formatter for AI system prompt placeholders."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from importlib import import_module
from typing import Any, Protocol, cast

import pendulum
from pendulum import DateTime as PendulumDateTime

from app.type_defs import InstanceContext
from app.utils.logging import get_logger

logger = get_logger(__name__)

_WEEKDAY_CN = ("一", "二", "三", "四", "五", "六", "日")
_WEEKEND_WEEKDAY_INDEX = 5

_HOLIDAY_DETAIL_MIN_LENGTH = 2
_HOLIDAY_DETAIL_NAME_INDEX = 1

_RELATIVE_YESTERDAY = -1
_RELATIVE_BEFORE_YESTERDAY = -2
_RELATIVE_TOMORROW = 1
_RELATIVE_AFTER_TOMORROW = 2

_DAY_PERIOD_BOUNDARIES: tuple[tuple[int, str], ...] = (
    (359, "凌晨"),
    (539, "早上"),
    (689, "上午"),
    (779, "中午"),
    (1079, "下午"),
    (1139, "傍晚"),
)
_DAY_PERIOD_DEFAULT = "晚上"


HolidayDetail = tuple[object, str, object] | str | None


class _GetHolidayDetailCallable(Protocol):
    """Protocol for chinese_calendar.get_holiday_detail."""

    def __call__(self, target_date: date) -> tuple[bool, HolidayDetail]: ...


class _JieQiLike(Protocol):
    """Protocol for lunar jieqi object."""

    def getName(self) -> str: ...


class _LunarLike(Protocol):
    """Protocol for lunar object methods used by this module."""

    def getYearInGanZhi(self) -> str: ...
    def getMonthInChinese(self) -> str: ...
    def getDayInChinese(self) -> str: ...
    def getYearShengXiao(self) -> str: ...
    def getFestivals(self) -> list[str]: ...
    def getCurrentJieQi(self) -> _JieQiLike | None: ...


class _SolarLike(Protocol):
    """Protocol for solar object methods used by this module."""

    def getLunar(self) -> _LunarLike: ...
    def getFestivals(self) -> list[str]: ...


class _SolarFactory(Protocol):
    """Protocol for solar factory methods used by this module."""

    def fromYmdHms(
        self,
        year: int,
        month: int,
        day: int,
        hour: int,
        minute: int,
        second: int,
    ) -> _SolarLike: ...

    def fromYmd(self, year: int, month: int, day: int) -> _SolarLike: ...


_chinese_calendar_module = import_module("chinese_calendar")
_lunar_python_module = import_module("lunar_python")
get_holiday_detail = cast(
    _GetHolidayDetailCallable,
    _chinese_calendar_module.get_holiday_detail,
)
LunarSolar = cast(_SolarFactory, _lunar_python_module.Solar)


@dataclass(frozen=True)
class LegalDayInfo:
    """Legal day classification for a calendar date."""

    day_type: str
    holiday_name: str | None


def build_current_datetime(context: dict[str, Any] | InstanceContext) -> str:
    """Build `current_datetime` placeholder text."""
    now, timezone_name = _resolve_now((context or {}).get("timezone"))
    sections = [
        _safe_section("today_line", lambda: _format_today_time_context(now)),
        _safe_section(
            "past_week_line",
            lambda: _format_week_time_context(now, timezone_name, is_past=True),
        ),
        _safe_section(
            "future_week_line",
            lambda: _format_week_time_context(now, timezone_name, is_past=False),
        ),
    ]
    return "\n".join(section for section in sections if section)


def _safe_section(name: str, builder: Callable[[], str]) -> str:
    """Build one section safely and return empty string on failure."""
    try:
        return builder()
    except Exception:
        logger.error("time_context_section_build_failed", section=name, exc_info=True)
        return ""


def _resolve_now(timezone_name: object | None) -> tuple[PendulumDateTime, str]:
    """Resolve current time with timezone fallback."""
    tz_name = str(timezone_name).strip() if timezone_name else "Asia/Shanghai"
    try:
        return pendulum.now(tz_name), tz_name
    except Exception:
        logger.warning("invalid_timezone_fallback", timezone=tz_name)
        fallback_tz = "Asia/Shanghai"
        return pendulum.now(fallback_tz), fallback_tz


def _format_today_time_context(now: PendulumDateTime) -> str:
    """Format today's one-line time context string."""
    current_date = date(year=now.year, month=now.month, day=now.day)
    weekday = _WEEKDAY_CN[now.day_of_week]
    day_period = _get_day_period(now.hour, now.minute)

    lunar_text = ""
    festivals: list[str] = []
    jie_qi_name: str | None = None
    legal_info = _resolve_legal_day_info(current_date)

    try:
        solar = LunarSolar.fromYmdHms(
            now.year,
            now.month,
            now.day,
            now.hour,
            now.minute,
            now.second,
        )
        lunar = solar.getLunar()
        lunar_text = (
            f"{lunar.getYearInGanZhi()}年"
            f"{lunar.getMonthInChinese()}{lunar.getDayInChinese()}"
            f"（{lunar.getYearShengXiao()}年）"
        )
        festivals = _deduplicate_preserve_order([*solar.getFestivals(), *lunar.getFestivals()])
        jie_qi_obj = lunar.getCurrentJieQi()
        jie_qi_name = jie_qi_obj.getName() if jie_qi_obj is not None else None
    except Exception:
        logger.error("time_context_lunar_section_failed", exc_info=True)

    if legal_info.day_type == "法定假" and legal_info.holiday_name:
        remaining_days = _count_remaining_holiday_days(current_date, legal_info.holiday_name)
        if remaining_days is not None:
            holiday_text = f"{legal_info.holiday_name}（假期还有{remaining_days}天）"
            if legal_info.holiday_name in festivals:
                festivals = [
                    holiday_text if item == legal_info.holiday_name else item for item in festivals
                ]
            else:
                festivals.append(holiday_text)

    event_tokens: list[str] = []
    if legal_info.day_type:
        event_tokens.append(legal_info.day_type)
    if jie_qi_name:
        event_tokens.append(jie_qi_name)
    event_tokens.extend(festivals)

    segments = [f"{now.year}年{now.month}月{now.day}日"]
    if lunar_text:
        segments.append(lunar_text)
    segments.append(f"星期{weekday}")
    segments.append(f"今天{'、'.join(event_tokens)}" if event_tokens else "今天")
    segments.append(f"{day_period}{now.format('h:mm')}（{now.format('HH:mm')}）")
    return " ".join(segments)


def _format_week_time_context(
    now: PendulumDateTime,
    timezone_name: str,
    *,
    is_past: bool,
) -> str:
    """Format past/future week event summaries."""
    offsets = range(-1, -8, -1) if is_past else range(1, 8)
    line_title = "过去一周" if is_past else "未来一周"

    summaries: list[str] = []
    for offset in offsets:
        target = now.add(days=offset).in_timezone(timezone_name)
        target_date = date(year=target.year, month=target.month, day=target.day)
        event_summary = _build_daily_event_summary(target_date)
        if event_summary is None:
            continue

        relative = _format_relative_label(offset)
        summaries.append(f"{target.month}月{target.day}日（{relative}）{event_summary}")

    if not summaries:
        return f"{line_title}：无"
    return f"{line_title}：" + "、".join(summaries)


def _build_daily_event_summary(target_date: date) -> str | None:
    """Build event summary text for a single day."""
    try:
        solar = LunarSolar.fromYmd(target_date.year, target_date.month, target_date.day)
        lunar = solar.getLunar()
        legal_info = _resolve_legal_day_info(target_date)

        events: list[str] = []
        if legal_info.day_type == "法定假":
            if legal_info.holiday_name:
                events.append(f"{legal_info.holiday_name}法定假")
            else:
                events.append("法定假")
        elif legal_info.day_type == "调休":
            events.append("调休")

        jie_qi_obj = lunar.getCurrentJieQi()
        if jie_qi_obj is not None:
            events.append(jie_qi_obj.getName())

        festival_names = _deduplicate_preserve_order([*solar.getFestivals(), *lunar.getFestivals()])
        for name in festival_names:
            if legal_info.day_type == "法定假" and legal_info.holiday_name == name:
                continue
            events.append(name)

        if not events:
            return None
        return "、".join(_deduplicate_preserve_order(events))
    except Exception:
        logger.error(
            "time_context_daily_event_summary_failed",
            date=str(target_date),
            exc_info=True,
        )
        return None


def _resolve_legal_day_info(target_date: date) -> LegalDayInfo:
    """Resolve legal day type and holiday name for a date."""
    try:
        on_holiday, holiday_value = get_holiday_detail(target_date)
        holiday_name = _extract_holiday_name(holiday_value)

        if on_holiday:
            day_type = "法定假" if holiday_name else "周末"
        elif holiday_name:
            day_type = "调休"
        else:
            day_type = "周末" if target_date.weekday() >= _WEEKEND_WEEKDAY_INDEX else "工作日"

        return LegalDayInfo(day_type=day_type, holiday_name=holiday_name)
    except Exception:
        logger.error(
            "time_context_legal_day_resolve_failed",
            date=str(target_date),
            exc_info=True,
        )
        return LegalDayInfo(day_type="", holiday_name=None)


def _extract_holiday_name(holiday_value: HolidayDetail) -> str | None:
    """Extract Chinese holiday name from chinese-calendar holiday detail."""
    if holiday_value is None:
        return None
    if isinstance(holiday_value, tuple) and len(holiday_value) >= _HOLIDAY_DETAIL_MIN_LENGTH:
        name = holiday_value[_HOLIDAY_DETAIL_NAME_INDEX]
        return name if isinstance(name, str) else None
    if isinstance(holiday_value, str):
        return holiday_value
    return None


def _count_remaining_holiday_days(current_date: date, holiday_name: str) -> int | None:
    """Count remaining days (including today) for the current legal holiday."""
    try:
        remaining = 0
        cursor = current_date
        while True:
            on_holiday, holiday_value = get_holiday_detail(cursor)
            if not on_holiday:
                break
            if _extract_holiday_name(holiday_value) != holiday_name:
                break

            remaining += 1
            cursor = cursor + timedelta(days=1)
        return remaining
    except Exception:
        logger.error(
            "time_context_holiday_remaining_days_failed",
            date=str(current_date),
            holiday_name=holiday_name,
            exc_info=True,
        )
        return None


def _deduplicate_preserve_order(values: list[str]) -> list[str]:
    """Deduplicate values while preserving insertion order."""
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _format_relative_label(day_offset: int) -> str:
    """Format relative day label for week summaries."""
    if day_offset == _RELATIVE_YESTERDAY:
        return "昨天"
    if day_offset == _RELATIVE_BEFORE_YESTERDAY:
        return "前天"
    if day_offset < 0:
        return f"{abs(day_offset)}天前"
    if day_offset == _RELATIVE_TOMORROW:
        return "明天"
    if day_offset == _RELATIVE_AFTER_TOMORROW:
        return "后天"
    return f"{day_offset}天后"


def _get_day_period(hour: int, minute: int) -> str:
    """Map clock time to Chinese day period."""
    total_minutes = hour * 60 + minute
    for upper_bound, period_name in _DAY_PERIOD_BOUNDARIES:
        if total_minutes <= upper_bound:
            return period_name
    return _DAY_PERIOD_DEFAULT
