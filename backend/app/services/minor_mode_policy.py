"""Minor-mode policy helpers."""

from __future__ import annotations

from app.models.user import User


def is_minor_mode_enabled(user: User | None) -> bool:
    """Return whether minor-mode filtering should be applied."""
    return bool(user and user.minor_mode_enabled)
