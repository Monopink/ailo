"""System-level type definitions."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from app.models.system import SystemConfig


class ConfigGroup(TypedDict):
    """Dynamic grouping of configuration items for admin display."""

    title: str
    description: str
    configs: dict[str, SystemConfig]


__all__ = ["ConfigGroup"]
