import pytest

from app.services.message.processing.buffer import _compute_buffer_expiration


def test_compute_buffer_expiration_without_wake_returns_timer_due() -> None:
    result = _compute_buffer_expiration(
        micro_expires_at_ms=1200,
        macro_expires_at_ms=1500,
        wake_delay_ms=None,
    )
    assert result == 1200


def test_compute_buffer_expiration_with_wake_uses_serial_composition() -> None:
    result = _compute_buffer_expiration(
        micro_expires_at_ms=1200,
        macro_expires_at_ms=1500,
        wake_delay_ms=300,
    )
    assert result == 1500


def test_compute_buffer_expiration_with_only_wake_uses_now_base() -> None:
    result = _compute_buffer_expiration(
        micro_expires_at_ms=None,
        macro_expires_at_ms=None,
        wake_delay_ms=400,
        now_ms=1000,
    )
    assert result == 1400


def test_compute_buffer_expiration_requires_now_when_only_wake_exists() -> None:
    with pytest.raises(ValueError, match="now_ms is required"):
        _compute_buffer_expiration(
            micro_expires_at_ms=None,
            macro_expires_at_ms=None,
            wake_delay_ms=100,
        )
