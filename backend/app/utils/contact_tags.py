"""Helpers for normalizing and validating contact tag payloads."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from app.type_defs import JSONValue

TAG_MAX_LENGTH = 20
TAG_MAX_COUNT = 20
TAG_MAX_TOTAL_LENGTH = 200


def extract_tags_payload(value: JSONValue | None) -> list[str] | None:
    """Extract a list of tag strings from a JSON payload.

    Accepts either a raw JSON array or a wrapped dict payload: {"tags": [...]}.
    Returns None when the payload is missing or does not match the expected format.
    """
    if value is None:
        return None

    items: object | None = None
    if isinstance(value, list):
        items = value
    elif isinstance(value, dict):
        items = value.get("tags")

    if not isinstance(items, list):
        return None

    return [item for item in items if isinstance(item, str)]


def normalize_tags(raw_tags: Sequence[str] | None) -> list[str] | None:
    """Normalize tags by trimming, dropping blanks, de-duplicating, and preserving order.

    Returns None when raw_tags is None ("not provided"). Otherwise returns a list of strings.
    The returned list may be empty, which represents an explicit empty value.
    """
    if raw_tags is None:
        return None

    seen: set[str] = set()
    normalized: list[str] = []
    for tag in raw_tags:
        stripped = tag.strip()
        if stripped == "":
            continue
        if stripped in seen:
            continue
        seen.add(stripped)
        normalized.append(stripped)
    return normalized


def compute_total_length(tags: Sequence[str]) -> int:
    """Compute total tag string length matching client calculation: tags.join(', ').length."""
    if not tags:
        return 0
    return len(", ".join(tags))


def validate_tags(tags: Sequence[str]) -> str | None:
    """Validate tags against size constraints.

    Returns a user-facing message when invalid, otherwise None.
    """
    if len(tags) > TAG_MAX_COUNT:
        return "请求参数错误"
    if any(len(tag) > TAG_MAX_LENGTH for tag in tags):
        return "请求参数错误"
    if compute_total_length(tags) > TAG_MAX_TOTAL_LENGTH:
        return "请求参数错误"
    return None


def is_string_list(value: object) -> bool:
    """Return True when value is a list[str]."""
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def filter_string_tags(value: Iterable[object] | None) -> list[str]:
    """Filter out non-string tags and return a list[str]."""
    if value is None:
        return []
    return [item for item in value if isinstance(item, str)]
