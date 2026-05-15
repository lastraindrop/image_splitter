# image_splitter/models.py
"""Configuration models for image processors."""
from dataclasses import dataclass
from typing import Any, List, Tuple


@dataclass
class SplitConfig:
    """Grid splitting configuration model.

    Attributes:
        rows: Number of rows to split.
        cols: Number of columns to split.
        output_dir: Output directory for results.
        template: Output filename template.
        offsets: Margin offsets (Left, Top, Right, Bottom).
    """
    rows: int
    cols: int
    output_dir: str
    template: str = "{filename}_{index}"
    offsets: Tuple[int, int, int, int] = (0, 0, 0, 0)

    def __post_init__(self) -> None:
        if not isinstance(self.rows, int) or not isinstance(self.cols, int):
            raise ValueError("Rows and columns must be integers")
        if not isinstance(self.offsets, (tuple, list)) or len(self.offsets) != 4:
            raise ValueError("Offsets must be a tuple or list of 4 integers")
        self.validate()

    def validate(self) -> None:
        if self.rows <= 0 or self.cols <= 0:
            raise ValueError("Rows and columns must be positive integers")
        if any(o < 0 for o in self.offsets):
            raise ValueError("Offsets cannot be negative")


@dataclass
class AdjustConfig:
    """Canvas adjustment configuration model."""
    width: Any
    height: Any
    output_dir: str
    anchor: str = "center"
    bg_color: Tuple[int, int, int, int] = (255, 255, 255, 255)
    template: str = "{filename}_adjusted"

    def __post_init__(self) -> None:
        if isinstance(self.width, str):
            self.width = float(self.width) if '.' in self.width else int(self.width)
        if isinstance(self.height, str):
            self.height = float(self.height) if '.' in self.height else int(self.height)
        self.validate()

    def validate(self) -> None:
        if not isinstance(self.width, (int, float)) or not isinstance(self.height, (int, float)):
            raise ValueError(
                f"Target width and height must be numbers "
                f"(Got {type(self.width)})"
            )
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Target width and height must be greater than 0")


@dataclass
class CustomSplitConfig:
    """Custom ratio splitting configuration model."""
    h_lines: List[int]
    v_lines: List[int]
    output_dir: str
    template: str = "{filename}_{row}_{col}"

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if not isinstance(self.h_lines, (list, tuple)) or not isinstance(self.v_lines, (list, tuple)):
            raise ValueError("Split lines must be in list or tuple format")
        if any(not isinstance(x, int) or x < 0 for x in self.h_lines + self.v_lines):
            raise ValueError("Split line coordinates must be non-negative integers")


@dataclass
class ColorConfig:
    """Color adjustment configuration model."""
    brightness: float = 1.0
    contrast: float = 1.0
    sharpness: float = 1.0
    color: float = 1.0


@dataclass
class FilterConfig:
    """Effect filter configuration model."""
    grayscale: bool = False
    invert: bool = False


@dataclass
class FormatConfig:
    """Format conversion configuration model."""
    format: str = "WebP"
    quality: int = 80


@dataclass
class ResizeConfig:
    """Image resizing configuration model."""
    width: float = 1.0
    height: float = 1.0

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Resize ratio must be greater than 0")


@dataclass
class GeometryConfig:
    """Geometry transformation configuration model."""
    rotate: int = 0
    flip_h: bool = False
    flip_v: bool = False


@dataclass
class MetadataConfig:
    """Metadata cleaning configuration model."""
    strip_all: bool = True
    keep_icc: bool = True


@dataclass
class WatermarkConfig:
    """Text watermark configuration model."""
    text: str = ""
    size: int = 40
    opacity: int = 128
    anchor: str = "BR"
