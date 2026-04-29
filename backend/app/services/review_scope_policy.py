"""Review-scope policies for visibility and capability decisions."""

from __future__ import annotations

from app.enums import ReviewScope, SquareCategoryReviewVisibilityScope
from app.models.user import User


def resolve_effective_review_scope(user: User | None) -> ReviewScope:
    """Resolve effective review scope with safe fallback."""
    if user is None:
        return ReviewScope.NON_REVIEW

    try:
        return ReviewScope(int(user.review_scope))
    except (TypeError, ValueError):
        return ReviewScope.NON_REVIEW


def resolve_visible_review_scopes(user: User | None) -> tuple[int, ...]:
    """Return allowed review-visibility scopes for current user."""
    review_scope = resolve_effective_review_scope(user)
    if review_scope == ReviewScope.MP_WEIXIN_REVIEW:
        return (
            int(SquareCategoryReviewVisibilityScope.ALL_USERS),
            int(SquareCategoryReviewVisibilityScope.ALL_REVIEWERS),
            int(SquareCategoryReviewVisibilityScope.MP_WEIXIN_REVIEWERS),
        )
    return (
        int(SquareCategoryReviewVisibilityScope.ALL_USERS),
        int(SquareCategoryReviewVisibilityScope.REGULAR_USERS),
    )


def is_invitation_capability_allowed(user: User) -> bool:
    """Whether current user can use invitation capability."""
    return resolve_effective_review_scope(user) == ReviewScope.NON_REVIEW
