"""Admin system enums."""

from enum import IntEnum


class AdminRole(IntEnum):
    """Administrator role (admin_users.role)."""

    SUPER_ADMIN = 1
    ADMIN = 2
    VIEWER = 3  # Read-only


class AdminStatus(IntEnum):
    """Administrator status (admin_users.status)."""

    ACTIVE = 1
    INACTIVE = 2


class AdminOperationType(IntEnum):
    """Admin operation type (admin_operation_logs.operation_type)."""

    CREATE = 1
    UPDATE = 2
    DELETE = 3
    ENABLE = 4
    DISABLE = 5
    REFRESH = 6  # E.g., refresh system conversation
    QUERY = 7  # For sensitive queries only
    EXECUTE = 8  # E.g., execute test
    EXPORT = 9
    IMPORT = 10


class AdminLoginResult(IntEnum):
    """Admin login result (admin_login_logs.result)."""

    SUCCESS = 1
    FAIL = 2
