import logging
import logging.handlers
import re
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Protocol, cast

import structlog
from structlog.processors import CallsiteParameter, CallsiteParameterAdder
from structlog.typing import EventDict, Processor, WrappedLogger

_REDACTED_VALUE = "***"
_SENSITIVE_QUERY_KEYS = (
    "secret",
    "access_token",
    "refresh_token",
    "id_token",
    "token",
    "api_key",
    "apikey",
    "api-key",
    "x-api-key",
    "x_api_key",
    "authorization",
    "proxy-authorization",
    "password",
    "signature",
    "js_code",
    "login_code",
    "phone_code",
    "sms_code",
)

_QUERY_KEY_PATTERN = "|".join(re.escape(key) for key in _SENSITIVE_QUERY_KEYS)
_REDACTION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # URL query parameters: ...?secret=xxx&... or ...&access_token=xxx
    (re.compile(rf"(?i)([?&](?:{_QUERY_KEY_PATTERN})=)[^&\s]+"), rf"\1{_REDACTED_VALUE}"),
    # Authorization headers (redact everything after the separator).
    (re.compile(r"(?i)(\bauthorization\b\s*[:=]\s*)([^,\r\n]+)"), rf"\1{_REDACTED_VALUE}"),
    (re.compile(r"(?i)(\bproxy-authorization\b\s*[:=]\s*)([^,\r\n]+)"), rf"\1{_REDACTED_VALUE}"),
    # Bearer tokens that may appear without an explicit header key.
    (re.compile(r"(?i)\bbearer\s+[^\s,;\"']+"), f"Bearer {_REDACTED_VALUE}"),
    # Plain key=value fragments (non-URL context)
    (re.compile(rf"(?i)(\b(?:{_QUERY_KEY_PATTERN})=)[^\s&]+"), rf"\1{_REDACTED_VALUE}"),
    # Plain key: value fragments
    (re.compile(rf"(?i)(\b(?:{_QUERY_KEY_PATTERN})\b\s*:\s*)[^\s,;\"']+"), rf"\1{_REDACTED_VALUE}"),
    # JSON-like key/value fragments: "secret": "xxx"
    (
        re.compile(rf'(?i)("(?:(?:{_QUERY_KEY_PATTERN}))"\s*:\s*")([^"]*)(")'),
        rf"\1{_REDACTED_VALUE}\3",
    ),
)


def redact_sensitive_text(text: str) -> str:
    """Redact sensitive tokens/secrets from arbitrary text before logging."""
    redacted = text
    for pattern, replacement in _REDACTION_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def _redact_value(value: object) -> object:
    if isinstance(value, str):
        return redact_sensitive_text(value)
    if isinstance(value, Mapping):
        return {key: _redact_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_value(item) for item in value)
    return value


def redact_structlog_event(_logger: WrappedLogger, _name: str, event_dict: EventDict) -> EventDict:
    """Structlog processor to redact sensitive fields from event dictionaries."""
    for key, value in list(event_dict.items()):
        event_dict[key] = _redact_value(value)
    return event_dict


class SensitiveDataRedactionFilter(logging.Filter):
    """Logging filter to redact sensitive data from stdlib log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact sensitive data from LogRecord before formatting/output."""
        try:
            if isinstance(record.msg, str):
                record.msg = redact_sensitive_text(record.msg)
            elif isinstance(record.msg, (Mapping, list, tuple)):
                record.msg = _redact_value(record.msg)
            if record.args:
                if isinstance(record.args, tuple):
                    record.args = tuple(_redact_value(arg) for arg in record.args)
                elif isinstance(record.args, dict):
                    record.args = {key: _redact_value(value) for key, value in record.args.items()}
        except Exception:
            # Never break application logging due to redaction issues.
            return True
        return True


def format_log_level(_logger: WrappedLogger, _name: str, event_dict: EventDict) -> EventDict:
    """Map python log levels to short uppercase names.

    e.g., 'warning' -> 'WARN', 'critical' -> 'FATAL'
    """
    level_map = {
        "warning": "WARN",
        "critical": "FATAL",
    }
    level = event_dict.get("level")
    if isinstance(level, str):
        # Use mapped value if available, otherwise just uppercase the level
        event_dict["level"] = level_map.get(level, level.upper())
    return event_dict


def configure_logging(
    log_level: str = "INFO",
    log_format: str = "json",
    log_dir: str = "./logs",
    service_name: str = "backend",
) -> None:
    """Configure structured logging for the backend.

    This setup ensures that logs are processed as JSON and saved to files.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Log format (json, text)
        log_dir: Directory to store log files
        service_name: Name of the service for log identification

    """
    # Ensure logs directory exists
    log_dir_path = Path(log_dir)
    log_dir_path.mkdir(parents=True, exist_ok=True)

    # Convert string log level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Configure file handler with rotation
    log_file = log_dir_path / f"{service_name}.log"
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",  # 10MB
    )
    file_handler.setLevel(numeric_level)

    # Configure console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)

    redaction_filter = SensitiveDataRedactionFilter()
    file_handler.addFilter(redaction_filter)
    console_handler.addFilter(redaction_filter)

    # Configure root logger
    logging.basicConfig(
        level=numeric_level, format="%(message)s", handlers=[file_handler, console_handler]
    )

    # Silence noisy third-party HTTP client request logs (never log full URLs with query strings).
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    # Choose processors based on format
    if log_format.lower() == "json":
        processors: list[Processor] = [
            structlog.stdlib.add_log_level,
            format_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            CallsiteParameterAdder(
                {
                    CallsiteParameter.MODULE,
                    CallsiteParameter.FUNC_NAME,
                    CallsiteParameter.LINENO,
                }
            ),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            redact_structlog_event,
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ]
    else:
        # Text format for development
        processors = [
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            redact_structlog_event,
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    logger = get_logger(__name__)
    logger.info(
        "logging_configured_successfully",
        log_file=log_file,
        service=service_name,
        level=log_level,
        format=log_format,
    )


class BoundLoggerProtocol(Protocol):
    """Subset of structlog BoundLogger used by the application."""

    def bind(self, **kwargs: object) -> "BoundLoggerProtocol":
        """Bind context data to the logger."""
        ...

    def debug(self, event: str, **kwargs: object) -> object:
        """Log a debug-level event."""
        ...

    def info(self, event: str, **kwargs: object) -> object:
        """Log an info-level event."""
        ...

    def warning(self, event: str, **kwargs: object) -> object:
        """Log a warning-level event."""
        ...

    def error(self, event: str, **kwargs: object) -> object:
        """Log an error-level event."""
        ...

    def critical(self, event: str, **kwargs: object) -> object:
        """Log a critical-level event."""
        ...

    def exception(self, event: str, **kwargs: object) -> object:
        """Log an exception event."""
        ...


def get_logger(name: str | None = None) -> BoundLoggerProtocol:
    """Get a preconfigured structured logger.

    Args:
        name: Name of the logger, defaults to calling module name

    Returns:
        structlog.BoundLogger: The structured logger instance

    """
    logger = structlog.get_logger(name)
    return cast(BoundLoggerProtocol, logger)


def bind_context(logger: BoundLoggerProtocol, **kwargs: object) -> BoundLoggerProtocol:
    """Bind context data to a logger.

    Args:
        logger: The logger to bind context to
        **kwargs: Key-value pairs to bind

    Returns:
        structlog.BoundLogger: A new logger with bound context

    """
    return logger.bind(**kwargs)


def log_with_context(
    logger: BoundLoggerProtocol,
    level: str,
    event: str,
    context: Mapping[str, object] | None = None,
    **kwargs: object,
) -> None:
    """Log an event with context.

    Args:
        logger: The structured logger
        level: Log level (debug, info, warning, error, critical)
        event: Event description
        context: Additional context data
        **kwargs: Other key-value pairs to log

    """
    log_method = cast(Callable[..., object], getattr(logger, level))

    if context:
        kwargs.update(context)

    log_method(event, **kwargs)
