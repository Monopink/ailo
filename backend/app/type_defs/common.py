"""Shared JSON-compatible type aliases for the backend application.

This module centralizes recursive JSON type hints so that business logic
can import them from a single place (`app.types`).
"""

from __future__ import annotations

from typing import TypedDict

type JSONPrimitive = str | int | float | bool | None
type JSONValue = JSONPrimitive | list[JSONValue] | dict[str, JSONValue]
type JSONDict = dict[str, JSONValue]
type JSONArray = list[JSONValue]


class SnowflakeComponents(TypedDict):
    """Decomposed fields of a Snowflake-style identifier."""

    timestamp: int
    datetime: str
    datacenter_id: int
    machine_id: int
    sequence: int


__all__ = ["JSONArray", "JSONDict", "JSONPrimitive", "JSONValue", "SnowflakeComponents"]
