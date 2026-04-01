"""Discovery and square-related enums."""

from enum import IntEnum, StrEnum


class SquareEntryStatus(IntEnum):
    """Square exposure status (square_type_entries.status)."""

    ACTIVE = 1
    INACTIVE = 2


class SquareCategoryStatus(IntEnum):
    """Square category status (square_categories.status)."""

    ACTIVE = 1
    INACTIVE = 2


class SquareCategoryTheme(StrEnum):
    """Square category theme keys (source of truth for square_categories.theme_key)."""

    BLUE = "blue"
    CYAN = "cyan"
    TEAL = "teal"
    GREEN = "green"
    LIME = "lime"
    YELLOW = "yellow"
    ORANGE = "orange"
    PURPLE = "purple"
    PINK = "pink"
    MAGENTA = "magenta"
    BEIGE = "beige"
    CHARCOAL = "charcoal"


SQUARE_CATEGORY_THEME_KEYS: tuple[str, ...] = tuple(item.value for item in SquareCategoryTheme)
SQUARE_CATEGORY_THEME_KEY_SET: frozenset[str] = frozenset(SQUARE_CATEGORY_THEME_KEYS)


def is_valid_square_category_theme(value: str) -> bool:
    """Check whether value is a valid square category theme key."""
    return value in SQUARE_CATEGORY_THEME_KEY_SET


class ExposureStrategy(IntEnum):
    """Square exposure strategy (square_type_entries.exposure_strategy)."""

    RANDOM = 1  # Randomized ordering (default). Other strategies are not supported yet.
