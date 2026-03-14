"""Test log redaction utilities to avoid leaking secrets/tokens."""

import logging

from app.utils.logging import (
    SensitiveDataRedactionFilter,
    redact_sensitive_text,
    redact_structlog_event,
)


def test_redact_sensitive_text_redacts_query_params() -> None:
    raw = (
        "HTTP Request: GET https://api.weixin.qq.com/sns/jscode2session"
        "?appid=wx123&secret=abc123&js_code=xyz987&grant_type=authorization_code"
    )
    redacted = redact_sensitive_text(raw)

    assert "abc123" not in redacted
    assert "xyz987" not in redacted
    assert "secret=***" in redacted
    assert "js_code=***" in redacted


def test_redact_sensitive_text_redacts_authorization_header() -> None:
    raw = "Authorization: Bearer super.secret.token"
    redacted = redact_sensitive_text(raw)

    assert "super.secret.token" not in redacted
    assert "***" in redacted


def test_redaction_filter_redacts_log_record_msg_and_args() -> None:
    redaction_filter = SensitiveDataRedactionFilter()

    record_msg = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="secret=abc123",
        args=(),
        exc_info=None,
    )
    assert redaction_filter.filter(record_msg) is True
    assert "abc123" not in str(record_msg.msg)

    record_args = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="failed: %s",
        args=("Authorization: Bearer token123",),
        exc_info=None,
    )
    assert redaction_filter.filter(record_args) is True
    assert "token123" not in str(record_args.args)


def test_redact_structlog_event_redacts_nested_values() -> None:
    event = {
        "event": "wechat_httpx_error",
        "url": "https://api.weixin.qq.com/sns/jscode2session?secret=abc123&js_code=xyz",
        "detail": {"Authorization": "Bearer token123"},
    }

    redacted = redact_structlog_event(None, "test", event)  # type: ignore[arg-type]

    assert "abc123" not in str(redacted)
    assert "xyz" not in str(redacted)
    assert "token123" not in str(redacted)
