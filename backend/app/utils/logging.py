import logging
import logging.handlers
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Protocol, cast

import structlog
from structlog.processors import CallsiteParameter, CallsiteParameterAdder
from structlog.typing import EventDict, Processor, WrappedLogger


def format_log_level(_logger: WrappedLogger, _name: str, event_dict: EventDict) -> EventDict:
    """
    Map python log levels to short uppercase names.
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
    """
    Configure structured logging for the backend.
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

    # Configure root logger
    logging.basicConfig(
        level=numeric_level, format="%(message)s", handlers=[file_handler, console_handler]
    )

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
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ]
    else:
        # Text format for development
        processors = [
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
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

    def bind(self, **kwargs: object) -> "BoundLoggerProtocol": ...
    def debug(self, event: str, **kwargs: object) -> object: ...
    def info(self, event: str, **kwargs: object) -> object: ...
    def warning(self, event: str, **kwargs: object) -> object: ...
    def error(self, event: str, **kwargs: object) -> object: ...
    def critical(self, event: str, **kwargs: object) -> object: ...
    def exception(self, event: str, **kwargs: object) -> object: ...


def get_logger(name: str | None = None) -> BoundLoggerProtocol:
    """
    Get a preconfigured structured logger

    Args:
        name: Name of the logger, defaults to calling module name

    Returns:
        structlog.BoundLogger: The structured logger instance
    """
    logger = structlog.get_logger(name)
    return cast(BoundLoggerProtocol, logger)


def bind_context(logger: BoundLoggerProtocol, **kwargs: object) -> BoundLoggerProtocol:
    """
    Bind context data to a logger

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
    """
    Log an event with context

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
