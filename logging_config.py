# image_splitter/logging_config.py
"""统一日志配置模块"""
import logging
import sys

DEFAULT_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging(
    level: str = "WARNING",
    format_string: str = DEFAULT_FORMAT,
    date_format: str = DEFAULT_DATE_FORMAT,
) -> None:
    """配置全局日志系统。

    Args:
        level: 日志级别，可选值 DEBUG/INFO/WARNING/ERROR/CRITICAL
        format_string: 日志格式字符串
        date_format: 日期时间格式
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
    """获取项目专用的日志记录器。

    Args:
        name: 日志记录器名称

    Returns:
        配置好的日志记录器
    """
    return logging.getLogger(f"image_splitter.{name}")


def setup_default_logging() -> None:
    """设置默认日志配置 (启动时自动调用)"""
    configure_logging(level="WARNING")