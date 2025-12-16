"""
Lightweight runtime validation helpers for development mode.

The helpers in this module are intentionally minimal and only enforce
basic invariants (required field presence and primitive type checks) to
catch mistakes while constructing TypedDict structures during MVP stage.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import NoneType
from typing import Any, get_args, get_origin, get_type_hints

from app.core.config import get_settings

_PRIMITIVE_TYPES: tuple[type[Any], ...] = (str, int, float, bool)


def _flatten_annotation(annotation: Any) -> set[type[Any]]:
    """Return a set of primitive/None types contained in annotation."""

    origin = get_origin(annotation)
    if origin in (None, NoneType):
        return {annotation}

    if origin in (list, dict, Mapping):
        # Skip collection validation at this stage
        return set()

    if origin in (tuple, set, frozenset):
        return set()

    if origin in (NoneType,):
        return {NoneType}

    if origin is None:
        return {annotation}

    flattened: set[type[Any]] = set()
    for arg in get_args(annotation):
        flattened.update(_flatten_annotation(arg))
    return flattened


def _is_primitive_type(value: Any, expected: type[Any]) -> bool:
    """Return True if value matches expected primitive type."""

    if expected in _PRIMITIVE_TYPES:
        return isinstance(value, expected)
    if expected is NoneType:
        return value is None
    return True  # Non-primitive types are skipped


def validate_typed_dict(
    data: Mapping[str, Any], expected_type: type[Any], *, name: str | None = None
) -> None:
    """
    Validate a TypedDict instance in DEBUG mode.

    Checks:
        - Required fields exist
        - Primitive fields contain values of expected type

    Args:
        data: Runtime mapping to validate.
        expected_type: TypedDict definition class.
        name: Optional context label for error messages.

    Raises:
        ValueError: When required keys missing or primitive type mismatch.
    """

    settings = get_settings()
    if not settings.DEBUG:
        return

    expected_name = name or expected_type.__name__
    required_keys: set[str] = getattr(expected_type, "__required_keys__", set())

    missing = required_keys - data.keys()
    if missing:
        raise ValueError(f"{expected_name}: missing required fields {sorted(missing)}")

    hints = get_type_hints(expected_type, globalns=None, localns=None)
    for key, annotation in hints.items():
        if key not in data:
            continue
        flattened = _flatten_annotation(annotation)
        if not flattened:
            continue
        value = data[key]
        if not any(_is_primitive_type(value, primitive) for primitive in flattened):
            raise ValueError(
                f"{expected_name}.{key}: expected {annotation}, got {type(value).__name__}"
            )


__all__ = ["validate_typed_dict"]
