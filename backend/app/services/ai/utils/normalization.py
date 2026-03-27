"""
Pure normalization helpers for LLM response payloads.

These helpers are shared across orchestrators and must not access DB/session.
"""

from __future__ import annotations

from typing import cast

from app.type_defs import JSONDict, JSONValue

MAX_REFRESH_IDS_PER_TURN = 2


def _parse_refresh_memory_id(item: JSONValue) -> int | None:
    if isinstance(item, bool):
        return None
    if isinstance(item, int):
        return item
    if isinstance(item, str):
        stripped = item.strip()
        if stripped and stripped.isdigit():
            return int(stripped)
    return None


def normalize_memory_operations(value: JSONValue | None) -> JSONDict:
    """Normalize LLM-provided memory operations into canonical structure."""
    normalized: JSONDict = {"remove": [], "update": [], "refresh_ids": [], "add": []}
    if not isinstance(value, dict):
        return normalized

    remove_items = value.get("remove")
    if isinstance(remove_items, list):
        normalized["remove"] = [item for item in remove_items if isinstance(item, str) and item]

    update_items = value.get("update")
    if isinstance(update_items, list):
        updates: list[JSONDict] = []
        for item in update_items:
            if not isinstance(item, dict):
                continue
            old_content = item.get("old_content")
            new_content = item.get("new_content")
            if not isinstance(old_content, str) or not isinstance(new_content, str):
                continue
            entry: JSONDict = {"old_content": old_content, "new_content": new_content}
            new_importance = item.get("new_importance")
            if isinstance(new_importance, int | float):
                entry["new_importance"] = int(new_importance)
            updates.append(entry)
        normalized["update"] = cast(list[JSONValue], updates)

    refresh_ids_items = value.get("refresh_ids")
    if isinstance(refresh_ids_items, list):
        refresh_ids: list[int] = []
        seen: set[int] = set()
        for item in refresh_ids_items:
            memory_id = _parse_refresh_memory_id(item)
            if memory_id is None:
                continue
            if memory_id in seen:
                continue
            seen.add(memory_id)
            refresh_ids.append(memory_id)
            if len(refresh_ids) >= MAX_REFRESH_IDS_PER_TURN:
                break
        normalized["refresh_ids"] = cast(list[JSONValue], refresh_ids)

    add_items = value.get("add")
    if isinstance(add_items, list):
        additions: list[JSONDict] = []
        for item in add_items:
            if not isinstance(item, dict):
                continue
            memory_type = item.get("memory_type")
            content = item.get("content")
            importance = item.get("importance")
            if memory_type not in {"core", "recent"}:
                continue
            if not isinstance(content, str) or not content:
                continue
            if not isinstance(importance, int | float):
                continue
            additions.append(
                {
                    "memory_type": memory_type,
                    "content": content,
                    "importance": int(importance),
                }
            )
        normalized["add"] = cast(list[JSONValue], additions)

    return normalized


def normalize_score_payload(score_value: JSONValue | None) -> dict[str, int]:
    """Convert JSON payload into normalized integer mapping."""
    if not isinstance(score_value, dict):
        return {}

    normalized: dict[str, int] = {}
    for key, value in score_value.items():
        coerced_value = _coerce_score_value(value)
        if coerced_value is not None:
            normalized[str(key)] = coerced_value
    return normalized


def _coerce_score_value(value: JSONValue) -> int | None:
    """Convert JSON scalar score values into ints."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int | float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None
    return None
