"""Account-segment mapping at API boundary."""

from __future__ import annotations

from app.enums import ReviewScope
from app.models.user import User
from app.services.review_scope_policy import resolve_effective_review_scope


def resolve_account_segment(user: User | None) -> int:
    """Resolve API-facing account segment from review_scope.

    Mapping:
    - 0: member_full
    - 1: member_limited
    """
    if resolve_effective_review_scope(user) == ReviewScope.MP_WEIXIN_REVIEW:
        return 1
    return 0
