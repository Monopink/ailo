"""Security-related enums."""

from enum import IntEnum


class ViolationType(IntEnum):
    """Security violation type (user_violation_logs.violation_type)."""

    PROMPT_INJECTION = 1  # Prompt injection attack
    ABUSE_CONTENT = 2  # Abusive content
    SPAM = 3  # Spam message
    HARASSMENT = 4  # Harassment behavior
    OTHER = 5  # Other violation


class SeverityLevel(IntEnum):
    """Violation severity level (user_violation_logs.severity_level)."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class AutoAction(IntEnum):
    """Automatic action taken (user_violation_logs.auto_action_taken)."""

    NONE = 1
    WARNING = 2
    RESTRICT = 3
    SUSPEND = 4


class ManualReviewStatus(IntEnum):
    """Manual review status (user_violation_logs.manual_review_status)."""

    PENDING = 1  # Pending review
    CONFIRMED = 2  # Violation confirmed
    FALSE_POSITIVE = 3
    IGNORED = 4


class RiskLevel(IntEnum):
    """User risk level (user_risk_stats.current_risk_level)."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    BANNED = 4
