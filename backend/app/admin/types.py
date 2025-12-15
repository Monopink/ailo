"""Shared admin view data structures.

Defines strict TypedDict models used across admin views to keep
view-related data consistent and type-safe.
"""

from __future__ import annotations

from typing import TypedDict

from starlette.requests import Request

from app.core.type_aliases import JSONDict


class AIInstanceTestContext(TypedDict, total=False):
    """Context data for the AI instance test interface template."""

    request: Request
    instance_id: int
    page_title: str
    test_readiness: JSONDict | None
    llm_configs: list[JSONDict]
    error: str | None


class AIInstanceTestResponse(TypedDict, total=False):
    """Response data structure for AI instance test execution."""

    success: bool
    test_mode: str
    log_id: int
    instance_info: JSONDict
    instance_profile: JSONDict
    style: JSONDict
    personality: JSONDict
    instance_settings: JSONDict
    test_user_info: JSONDict
    test_user_profile: JSONDict
    conversation: JSONDict
    performance: JSONDict
    relationship_scores: list[JSONDict]
    request_payload: JSONDict
    history_messages: list[JSONDict]
    current_user_message: JSONDict
    response_body: JSONDict
    selected_relationship_after: JSONDict
    available_contacts: list[JSONDict]
    available_test_users: list[JSONDict]
    test_user_selection_locked: bool
    locked_test_user_qiao_id: str | None


__all__ = [
    "AIInstanceTestContext",
    "AIInstanceTestResponse",
]
