import structlog
from typing import Dict, Any, Optional


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
