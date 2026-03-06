"""Shared username validation rules.

This module centralizes username constraints so API/Admin paths stay aligned.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.system_config import get_config

USERNAME_PATTERN = r"^[A-Za-z][A-Za-z0-9_-]{4,19}$"
USERNAME_START_PATTERN = r"^[A-Za-z]"
USERNAME_ALLOWED_PATTERN = r"^[A-Za-z0-9_-]+$"
USERNAME_MIN_LENGTH = 5
USERNAME_MAX_LENGTH = 20
USERNAME_REGEX = re.compile(USERNAME_PATTERN)
USERNAME_START_REGEX = re.compile(USERNAME_START_PATTERN)
USERNAME_ALLOWED_REGEX = re.compile(USERNAME_ALLOWED_PATTERN)
USERNAME_HELP_TEXT = (
    "Optional. 5-20 characters. Must start with a letter. "
    "Allowed: letters, numbers, underscore, hyphen."
)


class UsernameValidationConfigError(Exception):
    """Raised when username validation config is invalid."""


class UsernameValidationReason(StrEnum):
    """Stable reason codes for username validation failures."""

    EMPTY = "USERNAME_EMPTY"
    LEADING_OR_TRAILING_SPACES = "USERNAME_LEADING_OR_TRAILING_SPACES"
    TOO_SHORT = "USERNAME_TOO_SHORT"
    TOO_LONG = "USERNAME_TOO_LONG"
    MUST_START_WITH_LETTER = "USERNAME_MUST_START_WITH_LETTER"
    INVALID_CHARACTERS = "USERNAME_INVALID_CHARACTERS"
    RESERVED = "USERNAME_RESERVED"


@dataclass(frozen=True, slots=True)
class UsernameValidationIssue:
    """Structured validation issue for API/Admin branching."""

    message: str
    reason: UsernameValidationReason


async def validate_username_or_issue(
    db: AsyncSession, username: str
) -> UsernameValidationIssue | None:
    """Validate username and return structured issue when invalid."""
    issue: UsernameValidationIssue | None = None

    if not username:
        issue = UsernameValidationIssue(
            message="Username cannot be empty",
            reason=UsernameValidationReason.EMPTY,
        )
    elif username.strip() != username:
        issue = UsernameValidationIssue(
            message="Username cannot start or end with spaces",
            reason=UsernameValidationReason.LEADING_OR_TRAILING_SPACES,
        )
    elif len(username) < USERNAME_MIN_LENGTH:
        issue = UsernameValidationIssue(
            message="Username must be at least 5 characters",
            reason=UsernameValidationReason.TOO_SHORT,
        )
    elif len(username) > USERNAME_MAX_LENGTH:
        issue = UsernameValidationIssue(
            message="Username must be at most 20 characters",
            reason=UsernameValidationReason.TOO_LONG,
        )
    elif USERNAME_START_REGEX.match(username) is None:
        issue = UsernameValidationIssue(
            message="Username must start with a letter",
            reason=UsernameValidationReason.MUST_START_WITH_LETTER,
        )
    elif (
        USERNAME_ALLOWED_REGEX.fullmatch(username) is None
        or USERNAME_REGEX.fullmatch(username) is None
    ):
        issue = UsernameValidationIssue(
            message="Username can only contain letters, numbers, underscore, or hyphen",
            reason=UsernameValidationReason.INVALID_CHARACTERS,
        )
    if issue is not None:
        return issue

    username_reserved_words = await get_config(
        db,
        key="username_reserved_words",
        required=True,
    )
    if not isinstance(username_reserved_words, list):
        raise UsernameValidationConfigError("System config username_reserved_words is invalid")

    reserved_words_lower: set[str] = set()
    for reserved_word in username_reserved_words:
        if not isinstance(reserved_word, str):
            raise UsernameValidationConfigError("System config username_reserved_words is invalid")
        reserved_words_lower.add(reserved_word.lower())

    if username.lower() in reserved_words_lower:
        return UsernameValidationIssue(
            message="Username is reserved and cannot be used",
            reason=UsernameValidationReason.RESERVED,
        )

    return None


async def validate_username_or_error(db: AsyncSession, username: str) -> str | None:
    """Validate username and return error text when invalid."""
    issue = await validate_username_or_issue(db, username)
    if issue is None:
        return None
    return issue.message
