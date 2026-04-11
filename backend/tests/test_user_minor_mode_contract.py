"""Contract tests for user minor mode helpers."""

import pytest
from fastapi import HTTPException

from app.api.v1.users import (
    MINOR_MODE_REASON_PIN_REQUIRED,
    _validate_minor_mode_pin_or_raise,
)


def test_validate_minor_mode_pin_accepts_4_digit_input() -> None:
    """PIN validator should accept trimmed 4-digit values."""
    assert _validate_minor_mode_pin_or_raise(" 1234 ") == "1234"


@pytest.mark.parametrize("pin", ["", "123", "12345", "12a4", "abcd"])
def test_validate_minor_mode_pin_rejects_invalid_values(pin: str) -> None:
    """PIN validator should reject non-4-digit values."""
    with pytest.raises(HTTPException) as exc_info:
        _validate_minor_mode_pin_or_raise(pin)

    assert exc_info.value.status_code == 400
    assert isinstance(exc_info.value.detail, dict)
    assert exc_info.value.detail.get("reason") == MINOR_MODE_REASON_PIN_REQUIRED
