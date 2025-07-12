import structlog
from typing import Dict, Any, Optional
import logging
from structlog.processors import CallsiteParameter, CallsiteParameterAdder
from structlog.types import EventDict


def format_log_level(_, __, event_dict: EventDict) -> EventDict:
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


def configure_logging():
    """
    Configure structured logging for the application.
    This setup ensures that logs are processed as JSON, which is ideal for
    containerized environments and log aggregation tools like Dozzle.
    """
    logging.basicConfig(level=logging.DEBUG, format="%(message)s")

    structlog.configure(
        processors=[
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
            structlog.dev.set_exc_info,
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    logger = get_logger(__name__)
    logger.info("logging_configured_successfully")


def get_logger(name: Optional[str] = None) -> structlog.BoundLogger:
    """
    Get a preconfigured structured logger

    Args:
        name: Name of the logger, defaults to calling module name

    Returns:
        structlog.BoundLogger: The structured logger instance
    """
    logger = structlog.get_logger(name)
    return logger


def bind_context(logger: structlog.BoundLogger, **kwargs) -> structlog.BoundLogger:
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
    logger: structlog.BoundLogger,
    level: str,
    event: str,
    context: Optional[Dict[str, Any]] = None,
    **kwargs
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
    log_method = getattr(logger, level)

    if context:
        kwargs.update(context)

    log_method(event, **kwargs)
