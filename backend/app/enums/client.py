"""Client identifier enums."""

from enum import StrEnum


class ClientType(StrEnum):
    """Supported X-Client values."""

    MINI_PROGRAM = "mini-program"


class LocaleCode(StrEnum):
    """Supported locale identifiers for API-facing content."""

    ZH_CN = "zh-CN"
