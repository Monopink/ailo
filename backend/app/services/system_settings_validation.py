"""Business validation rules for system settings updates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from ipaddress import ip_address

MP_WEIXIN_REVIEW_DEADLINE_AT_CONFIG_KEY = "mp_weixin_review_deadline_at"
MP_WEIXIN_REVIEW_BUILD_TIME_FROM_CONFIG_KEY = "mp_weixin_review_build_time_from"
MP_WEIXIN_REVIEW_BUILD_TIME_TO_CONFIG_KEY = "mp_weixin_review_build_time_to"
MP_WEIXIN_REVIEW_IP_BLACKLIST_CONFIG_KEY = "mp_weixin_review_ip_blacklist"
MP_WEIXIN_RELEASE_BUILD_IDS_CONFIG_KEY = "mp_weixin_release_build_ids"


@dataclass(frozen=True)
class ConfigValidationIssue:
    """Represents one semantic validation issue for a config key."""

    config_key: str
    error_code: str
    message: str


def _parse_optional_utc_datetime(value: object) -> datetime | None:
    parsed: datetime | None = None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        raw = value.strip()
        if raw == "":
            return None
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    else:
        parsed = parsed.astimezone(UTC)
    return parsed


def _validate_mp_weixin_review_deadline_monotonic(
    *,
    effective_values: dict[str, object],
    persisted_values: dict[str, object],
) -> list[ConfigValidationIssue]:
    new_deadline = _parse_optional_utc_datetime(
        effective_values.get(MP_WEIXIN_REVIEW_DEADLINE_AT_CONFIG_KEY)
    )
    old_deadline = _parse_optional_utc_datetime(
        persisted_values.get(MP_WEIXIN_REVIEW_DEADLINE_AT_CONFIG_KEY)
    )
    if new_deadline is None or old_deadline is None:
        return []
    if new_deadline < old_deadline:
        return [
            ConfigValidationIssue(
                config_key=MP_WEIXIN_REVIEW_DEADLINE_AT_CONFIG_KEY,
                error_code="deadline_rollback_not_allowed",
                message="审核周期截止时间不能早于当前已保存时间",
            )
        ]
    return []


def _validate_mp_weixin_review_build_time_range(
    *,
    effective_values: dict[str, object],
) -> list[ConfigValidationIssue]:
    time_from = _parse_optional_utc_datetime(
        effective_values.get(MP_WEIXIN_REVIEW_BUILD_TIME_FROM_CONFIG_KEY)
    )
    time_to = _parse_optional_utc_datetime(
        effective_values.get(MP_WEIXIN_REVIEW_BUILD_TIME_TO_CONFIG_KEY)
    )
    if time_from is None or time_to is None:
        return []
    if time_from > time_to:
        return [
            ConfigValidationIssue(
                config_key=MP_WEIXIN_REVIEW_BUILD_TIME_FROM_CONFIG_KEY,
                error_code="build_time_range_invalid",
                message="审核构建时间区间无效：开始时间不能晚于结束时间",
            ),
            ConfigValidationIssue(
                config_key=MP_WEIXIN_REVIEW_BUILD_TIME_TO_CONFIG_KEY,
                error_code="build_time_range_invalid",
                message="审核构建时间区间无效：结束时间不能早于开始时间",
            ),
        ]
    return []


def _validate_mp_weixin_review_ip_blacklist(
    *,
    effective_values: dict[str, object],
) -> list[ConfigValidationIssue]:
    raw_value = effective_values.get(MP_WEIXIN_REVIEW_IP_BLACKLIST_CONFIG_KEY)
    if raw_value is None:
        return []
    if not isinstance(raw_value, list):
        return [
            ConfigValidationIssue(
                config_key=MP_WEIXIN_REVIEW_IP_BLACKLIST_CONFIG_KEY,
                error_code="review_ip_blacklist_invalid",
                message="审核 IP 黑名单必须为字符串数组",
            )
        ]

    issues: list[ConfigValidationIssue] = []
    for item in raw_value:
        if not isinstance(item, str):
            issues.append(
                ConfigValidationIssue(
                    config_key=MP_WEIXIN_REVIEW_IP_BLACKLIST_CONFIG_KEY,
                    error_code="review_ip_blacklist_invalid",
                    message="审核 IP 黑名单包含非字符串项",
                )
            )
            continue
        value = item.strip()
        if value == "":
            issues.append(
                ConfigValidationIssue(
                    config_key=MP_WEIXIN_REVIEW_IP_BLACKLIST_CONFIG_KEY,
                    error_code="review_ip_blacklist_invalid",
                    message="审核 IP 黑名单包含空字符串项",
                )
            )
            continue
        try:
            ip_address(value)
        except ValueError:
            issues.append(
                ConfigValidationIssue(
                    config_key=MP_WEIXIN_REVIEW_IP_BLACKLIST_CONFIG_KEY,
                    error_code="review_ip_blacklist_invalid",
                    message=f"审核 IP 黑名单包含非法 IP：{value}",
                )
            )
    return issues


def _validate_mp_weixin_release_build_ids(
    *,
    effective_values: dict[str, object],
) -> list[ConfigValidationIssue]:
    raw_value = effective_values.get(MP_WEIXIN_RELEASE_BUILD_IDS_CONFIG_KEY)
    if raw_value is None:
        return []
    if not isinstance(raw_value, list):
        return [
            ConfigValidationIssue(
                config_key=MP_WEIXIN_RELEASE_BUILD_IDS_CONFIG_KEY,
                error_code="release_build_ids_invalid",
                message="正式版构建 ID 列表必须为字符串数组",
            )
        ]

    issues: list[ConfigValidationIssue] = []
    for item in raw_value:
        if not isinstance(item, str):
            issues.append(
                ConfigValidationIssue(
                    config_key=MP_WEIXIN_RELEASE_BUILD_IDS_CONFIG_KEY,
                    error_code="release_build_ids_invalid",
                    message="正式版构建 ID 列表包含非字符串项",
                )
            )
            continue
        value = item.strip()
        if value == "":
            issues.append(
                ConfigValidationIssue(
                    config_key=MP_WEIXIN_RELEASE_BUILD_IDS_CONFIG_KEY,
                    error_code="release_build_ids_invalid",
                    message="正式版构建 ID 列表包含空字符串项",
                )
            )
    return issues


def validate_operation_config_updates(
    effective_values: dict[str, object],
    *,
    persisted_values: dict[str, object],
) -> list[ConfigValidationIssue]:
    """Return operation-settings semantic validation issues."""
    issues: list[ConfigValidationIssue] = []
    issues.extend(
        _validate_mp_weixin_review_deadline_monotonic(
            effective_values=effective_values,
            persisted_values=persisted_values,
        )
    )
    issues.extend(_validate_mp_weixin_review_build_time_range(effective_values=effective_values))
    issues.extend(_validate_mp_weixin_review_ip_blacklist(effective_values=effective_values))
    issues.extend(_validate_mp_weixin_release_build_ids(effective_values=effective_values))
    return issues
