"""Security-related enums."""

from enum import IntEnum


class ViolationType(IntEnum):
    """Security violation type (user_violation_logs.violation_type)."""

    PROMPT_INJECTION = 1  # Prompt injection attack
    SQL_INJECTION = 2  # SQL injection probes
    COMMAND_INJECTION = 3  # Command injection probes
    PATH_TRAVERSAL = 4  # Malicious path traversal probes
    OTHER = 99  # Other violation


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


class DetectionSource(IntEnum):
    """Detection source (user_violation_logs.detection_source)."""

    AI = 1
    API_RUNTIME = 2
    API_AUTH = 3
    API_PUBLIC_INVITATION = 4
    NGINX = 5
    MIDDLEWARE = 6


class IPBlockScope(IntEnum):
    """IP block scope (security_ip_blocks.block_scope)."""

    SINGLE_IP = 1
    CIDR = 2


class IPBlockStatus(IntEnum):
    """IP block status (security_ip_blocks.status)."""

    ACTIVE = 1
    RELEASED = 2
    EXPIRED = 3
