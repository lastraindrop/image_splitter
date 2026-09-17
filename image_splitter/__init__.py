"""Image Splitter Pro - main package."""

__version__ = "0.8.0"

from .core import (
    batch_process_images,
    process_image,
    run_parallel_batch,
    split_image_core,
)
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
    "run_parallel_batch",
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
