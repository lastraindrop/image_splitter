"""Unified logging configuration module."""
import logging
import logging.handlers
import sys
from pathlib import Path

DEFAULT_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

LOG_DIR_NAME = ".image_splitter"
LOG_FILE_NAME = "gui.log"
LOG_MAX_BYTES = 1 * 1024 * 1024  # 1 MB per file
LOG_BACKUP_COUNT = 3


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


def setup_file_logging(
    level: str = "INFO",
    log_dir: Path | None = None,
) -> Path | None:
    """Attach a rotating file handler for GUI-mode diagnostics.

    V14: GUI users have no stderr visibility; exceptions and processor
    errors are now persisted to ``~/.image_splitter/logs/gui.log``
    (rotated at 1 MB, 3 backups kept).

    Args:
        level: File log level (INFO captures processor failures).
        log_dir: Override directory (used by tests).

    Returns:
        The log file path, or ``None`` when the handler could not be
        attached (e.g. read-only home directory).
    """
    try:
        if log_dir is None:
            log_dir = Path.home() / LOG_DIR_NAME / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / LOG_FILE_NAME

        file_handler = logging.handlers.RotatingFileHandler(
            log_path,
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
        file_handler.setFormatter(
            logging.Formatter(DEFAULT_FORMAT, datefmt=DEFAULT_DATE_FORMAT)
        )

        root_logger = logging.getLogger()
        root_logger.addHandler(file_handler)
        logging.getLogger("image_splitter").setLevel(
            getattr(logging, level.upper(), logging.INFO)
        )
        return log_path
    except OSError:
        return None


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
