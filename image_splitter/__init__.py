"""Image Splitter Pro - main package."""

__version__ = "0.7.1"

from .core import process_image, split_image_core, batch_process_images
from .logging_config import (
    configure_logging,
    get_logger,
    setup_default_logging,
    setup_file_logging,
)
from .models import (
    AdjustConfig,
    BorderConfig,
    ColorConfig,
    CustomSplitConfig,
    FilterConfig,
    FormatConfig,
    GeometryConfig,
    MetadataConfig,
    ResizeConfig,
    RoundedCornerConfig,
    SmartCropConfig,
    SplitConfig,
    WatermarkConfig,
)

__all__ = [
    "process_image",
    "split_image_core",
    "batch_process_images",
    "AdjustConfig",
    "BorderConfig",
    "ColorConfig",
    "CustomSplitConfig",
    "FilterConfig",
    "FormatConfig",
    "GeometryConfig",
    "MetadataConfig",
    "ResizeConfig",
    "RoundedCornerConfig",
    "SmartCropConfig",
    "SplitConfig",
    "WatermarkConfig",
    "configure_logging",
    "get_logger",
    "setup_default_logging",
    "setup_file_logging",
]
