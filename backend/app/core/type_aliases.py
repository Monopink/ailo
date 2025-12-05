"""
Shared JSON-compatible type aliases for the backend application.
"""

from __future__ import annotations

type JSONPrimitive = str | int | float | bool | None
type JSONValue = JSONPrimitive | list[JSONValue] | dict[str, JSONValue]
type JSONDict = dict[str, JSONValue]
type JSONArray = list[JSONValue]

__all__ = ["JSONArray", "JSONDict", "JSONPrimitive", "JSONValue"]
