"""Profile management enums."""

from enum import IntEnum


class Gender(IntEnum):
    """Gender classification (profiles.gender)."""

    MALE = 1
    FEMALE = 2
    OTHER = 3


class ProfileOwnerType(IntEnum):
    """Profile owner type (profiles.owner_type).

    Note: All user types (normal, official, virtual) use owner_type=1 (USER).
    The user_type field in users table distinguishes between them.
    """

    USER = 1  # User profile (includes normal, official, virtual users)
    AI_PERSONA = 2  # AI persona profile (shared by instances created from this persona)
    AI_INSTANCE = 3  # AI instance profile (only for manually created instances)


class ProfileModifierType(IntEnum):
    """Profile modifier type (user_profile_logs.modified_by_type)."""

    USER = 1
    ADMIN = 2
    SYSTEM = 3
