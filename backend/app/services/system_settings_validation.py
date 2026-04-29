"""Business validation rules for system settings updates."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConfigValidationIssue:
    """Represents one semantic validation issue for a config key."""

    config_key: str
    error_code: str
    message: str


def validate_operation_config_updates(
    _effective_values: dict[str, object],
) -> list[ConfigValidationIssue]:
    """Return operation-settings semantic validation issues.

    Review-mode specific semantic checks were removed. Current operation settings
    have no cross-field business constraints at this layer.
    """
    return []
