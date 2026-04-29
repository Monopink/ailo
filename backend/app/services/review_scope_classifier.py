"""Runtime review-scope classifier for mini-program traffic."""

from __future__ import annotations

from dataclasses import dataclass

from app.enums import ReviewScope

PRIMARY_REVIEW_SCOPE_UA_FEATURE = ("tencent_security_team", "tencent security team")
SECONDARY_REVIEW_SCOPE_UA_FEATURES: tuple[tuple[str, str], ...] = (
    ("xweb", "xweb/"),
    ("windows_wechat_runtime", "windowswechat/wmpf"),
    ("mini_program_windows", "miniprogramenv/windows"),
)
SECONDARY_REVIEW_SCOPE_MATCH_THRESHOLD = len(SECONDARY_REVIEW_SCOPE_UA_FEATURES)


@dataclass(frozen=True)
class RuntimeReviewScopeDecision:
    """Runtime review-scope decision produced by user-agent classification."""

    review_scope: ReviewScope
    matched_features: tuple[str, ...]

    @property
    def is_limited_scope(self) -> bool:
        return self.review_scope == ReviewScope.MP_WEIXIN_REVIEW


def classify_runtime_review_scope(user_agent: str | None) -> RuntimeReviewScopeDecision:
    """Classify review scope by runtime user-agent feature matching."""
    normalized_ua = (user_agent or "").strip().lower()
    if normalized_ua == "":
        return RuntimeReviewScopeDecision(
            review_scope=ReviewScope.NON_REVIEW,
            matched_features=(),
        )

    matched_features: list[str] = []

    primary_name, primary_token = PRIMARY_REVIEW_SCOPE_UA_FEATURE
    if primary_token in normalized_ua:
        matched_features.append(primary_name)

    for feature_name, feature_token in SECONDARY_REVIEW_SCOPE_UA_FEATURES:
        if feature_token in normalized_ua:
            matched_features.append(feature_name)

    is_limited_scope = False
    if primary_name in matched_features:
        is_limited_scope = True
    else:
        secondary_hit_count = len(
            [name for name, _ in SECONDARY_REVIEW_SCOPE_UA_FEATURES if name in matched_features]
        )
        is_limited_scope = secondary_hit_count >= SECONDARY_REVIEW_SCOPE_MATCH_THRESHOLD

    return RuntimeReviewScopeDecision(
        review_scope=ReviewScope.MP_WEIXIN_REVIEW if is_limited_scope else ReviewScope.NON_REVIEW,
        matched_features=tuple(dict.fromkeys(matched_features)),
    )
