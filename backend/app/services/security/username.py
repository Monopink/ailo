"""Shared username validation rules.

This module centralizes username constraints so API/Admin paths stay aligned.
"""

from __future__ import annotations

import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.system_config import get_config

USERNAME_PATTERN = r"^(?!.*[_-]{2})[A-Za-z][A-Za-z0-9_-]{4,19}$"
USERNAME_REGEX = re.compile(USERNAME_PATTERN)
USERNAME_HELP_TEXT = (
    "Optional. 5-20 characters. Must start with a letter. "
    "Allowed: letters, numbers, underscore, hyphen. "
    "No consecutive separators (__ -- _- -_)"
)


class UsernameValidationConfigError(Exception):
    """Raised when username validation config is invalid."""


async def validate_username_or_error(db: AsyncSession, username: str) -> str | None:
    """Validate username and return error text when invalid."""
    if not username:
        return "Username cannot be empty"
    if username.strip() != username:
        return "Username cannot start or end with spaces"
    if not USERNAME_REGEX.fullmatch(username):
        return (
            "Username must be 5-20 characters, start with a letter, and contain only "
            "letters, numbers, underscore, or hyphen. Consecutive separators are not allowed."
        )

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
        return "Username is reserved and cannot be used"

    return None
