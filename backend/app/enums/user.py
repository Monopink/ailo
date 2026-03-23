"""User management enums.

All enum values correspond to the integer values defined in the database schema.
"""

from enum import IntEnum


class UserStatus(IntEnum):
    """User account status (users.status)."""

    ACTIVE = 1  # Normal active user
    DEACTIVATED = 2  # Account deactivated (user-initiated)
    SUSPENDED = 3  # Account suspended (admin-initiated)


class UserType(IntEnum):
    """User type classification (users.user_type).

    Design document standard: 1=normal, 2=official, 3=virtual (test/virtual user)
    """

    NORMAL = 1  # Regular user
    OFFICIAL = 2  # Official account
    VIRTUAL = 3  # Virtual user (for AI testing)


class UserTokenStatus(IntEnum):
    """User token status (user_tokens.status)."""

    ACTIVE = 1
    REVOKED = 2


class UserAuthStatus(IntEnum):
    """Third-party auth binding status (user_auths.status)."""

    ACTIVE = 1
    REVOKED = 2


class DeviceType(IntEnum):
    """Device type for sessions and login records."""

    IOS = 1
    ANDROID = 2
    WEB = 3
    MINI_PROGRAM = 4


class LoginType(IntEnum):
    """Login method (login_records.login_type)."""

    PASSWORD = 1
    SMS = 2
    WECHAT = 3
    APPLE = 4


class AuthType(IntEnum):
    """Third-party identity provider type (user_auths.auth_type)."""

    APPLE = 1
    QQ = 2
    WECHAT = 3


class LoginResult(IntEnum):
    """Login attempt result (login_records.result)."""

    SUCCESS = 1
    FAIL = 2
