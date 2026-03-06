"""Text metric helpers for user-editable profile/contact fields."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

ZWJ_CODE_POINT = 0x200D
VARIATION_SELECTOR_RANGES: Final[tuple[tuple[int, int], ...]] = (
    (0xFE00, 0xFE0F),
    (0xE0100, 0xE01EF),
)
EMOJI_MODIFIER_RANGES: Final[tuple[tuple[int, int], ...]] = ((0x1F3FB, 0x1F3FF),)
REGIONAL_INDICATOR_RANGES: Final[tuple[tuple[int, int], ...]] = ((0x1F1E6, 0x1F1FF),)
COMBINING_MARK_RANGES: Final[tuple[tuple[int, int], ...]] = (
    (0x0300, 0x036F),
    (0x1AB0, 0x1AFF),
    (0x1DC0, 0x1DFF),
    (0x20D0, 0x20FF),
    (0xFE20, 0xFE2F),
)
WIDE_OR_EMOJI_POINTS: Final[frozenset[int]] = frozenset((0x2329, 0x232A))
WIDE_OR_EMOJI_RANGES: Final[tuple[tuple[int, int], ...]] = (
    (0x1100, 0x115F),
    (0x2E80, 0x303E),
    (0x3040, 0x30FF),
    (0x3100, 0x312F),
    (0x3130, 0x318F),
    (0x3190, 0x31EF),
    (0x3200, 0x32FF),
    (0x3300, 0x4DBF),
    (0x4E00, 0xA4CF),
    (0xAC00, 0xD7A3),
    (0xF900, 0xFAFF),
    (0xFE10, 0xFE19),
    (0xFE30, 0xFE6F),
    (0xFF01, 0xFF60),
    (0xFFE0, 0xFFE6),
    (0x2600, 0x27BF),
    (0x1F300, 0x1FAFF),
)


@dataclass(frozen=True)
class TextLimitRule:
    """Validation rule for a user-editable text field."""

    field_label: str
    display_width_limit: int
    grapheme_limit: int


PROFILE_NICKNAME_RULE = TextLimitRule(
    field_label="昵称",
    display_width_limit=24,
    grapheme_limit=32,
)

PROFILE_BIO_RULE = TextLimitRule(
    field_label="个性签名",
    display_width_limit=120,
    grapheme_limit=120,
)

CONTACT_ALIAS_RULE = TextLimitRule(
    field_label="备注",
    display_width_limit=24,
    grapheme_limit=32,
)

CONTACT_REMARK_RULE = TextLimitRule(
    field_label="描述",
    display_width_limit=400,
    grapheme_limit=400,
)


def _is_in_ranges(code_point: int, ranges: tuple[tuple[int, int], ...]) -> bool:
    return any(start <= code_point <= end for start, end in ranges)


def _is_variation_selector(code_point: int) -> bool:
    return _is_in_ranges(code_point, VARIATION_SELECTOR_RANGES)


def _is_emoji_modifier(code_point: int) -> bool:
    return _is_in_ranges(code_point, EMOJI_MODIFIER_RANGES)


def _is_regional_indicator(code_point: int) -> bool:
    return _is_in_ranges(code_point, REGIONAL_INDICATOR_RANGES)


def _is_combining_mark(code_point: int) -> bool:
    return _is_in_ranges(code_point, COMBINING_MARK_RANGES)


def _is_wide_or_emoji(code_point: int) -> bool:
    return code_point in WIDE_OR_EMOJI_POINTS or _is_in_ranges(code_point, WIDE_OR_EMOJI_RANGES)


def get_text_metrics(text: str) -> tuple[int, int]:
    """Return (grapheme_count, display_width) with emoji/CJK-aware heuristics."""
    grapheme_count = 0
    display_width = 0
    join_next = False
    regional_pair_open = False

    for char in text:
        code_point = ord(char)

        if code_point == ZWJ_CODE_POINT:
            join_next = True
            regional_pair_open = False
            continue

        if (
            _is_combining_mark(code_point)
            or _is_variation_selector(code_point)
            or _is_emoji_modifier(code_point)
        ):
            continue

        if join_next:
            join_next = False
            regional_pair_open = False
            continue

        if _is_regional_indicator(code_point):
            if regional_pair_open:
                regional_pair_open = False
                continue
            regional_pair_open = True
            grapheme_count += 1
            display_width += 2
            continue

        regional_pair_open = False
        grapheme_count += 1
        display_width += 2 if _is_wide_or_emoji(code_point) else 1

    return grapheme_count, display_width


def validate_text_limit(value: str, rule: TextLimitRule) -> str | None:
    """Validate a text value against grapheme and display-width limits."""
    grapheme_count, display_width = get_text_metrics(value)
    if display_width > rule.display_width_limit:
        max_cn = rule.display_width_limit // 2
        return f"{rule.field_label}长度过长，最多{max_cn}个中文或{rule.display_width_limit}个英文"
    if grapheme_count > rule.grapheme_limit:
        return f"{rule.field_label}最多{rule.grapheme_limit}个字符"
    return None
