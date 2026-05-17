"""Unified logging configuration module."""
import logging
import sys

DEFAULT_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging(
    level: str = "WARNING",
    format_string: str = DEFAULT_FORMAT,
    date_format: str = DEFAULT_DATE_FORMAT,
) -> None:
    """Configure global logging system.

    Args:
        level: Log level, optional values DEBUG/INFO/WARNING/ERROR/CRITICAL
        format_string: Log format string
        date_format: Date time format
    """
    log_level = getattr(logging, level.upper(), logging.WARNING)

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(log_level)

    formatter = logging.Formatter(format_string, datefmt=date_format)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    logging.getLogger("image_splitter").setLevel(log_level)


def get_logger(name: str) -> logging.Logger:
    """Get project-specific logger.

    Args:
        name: Logger name

    Returns:
        Configured logger
    """
    return logging.getLogger(f"image_splitter.{name}")


def setup_default_logging() -> None:
    """Set default logging configuration (called automatically on startup)"""
    configure_logging(level="WARNING")