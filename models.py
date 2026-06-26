"""Configuration models for image processors."""
from dataclasses import dataclass, field
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
    rows: int = field(default=3, metadata={"label": "Rows"})
    cols: int = field(default=3, metadata={"label": "Cols"})
    output_dir: str = "./output"
    template: str = "{filename}_{index}"
    offsets: Tuple[int, int, int, int] = field(
        default=(0, 0, 0, 0), metadata={"label": "Offsets (L,T,R,B)"}
    )

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
    output_dir: str = "./output"
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
    h_lines: List[int] = field(
        default_factory=lambda: [50], metadata={"label": "Horizontal Lines"}
    )
    v_lines: List[int] = field(
        default_factory=lambda: [50], metadata={"label": "Vertical Lines"}
    )
    output_dir: str = "./output"
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
    brightness: float = field(default=1.0, metadata={"label": "Brightness"})
    contrast: float = field(default=1.0, metadata={"label": "Contrast"})
    sharpness: float = field(default=1.0, metadata={"label": "Sharpness"})
    color: float = field(default=1.0, metadata={"label": "Color/Saturation"})


@dataclass
class FilterConfig:
    """Effect filter configuration model."""
    grayscale: bool = field(default=False, metadata={"label": "Grayscale"})
    invert: bool = field(default=False, metadata={"label": "Invert"})


@dataclass
class FormatConfig:
    """Format conversion configuration model."""
    format: str = field(
        default="WebP",
        metadata={"label": "Target Format", "options": ["WebP", "JPEG", "PNG", "BMP"]},
    )
    quality: int = field(default=80, metadata={"label": "Quality (1-100)"})

    def __post_init__(self) -> None:
        valid_formats = {"WebP", "JPEG", "PNG", "BMP"}
        if self.format not in valid_formats:
            raise ValueError(
                f"Unsupported format: {self.format}. "
                f"Valid options: {sorted(valid_formats)}"
            )
        if not isinstance(self.quality, int) or not (1 <= self.quality <= 100):
            raise ValueError("Quality must be an integer between 1 and 100")


@dataclass
class ResizeConfig:
    """Image resizing configuration model."""
    width: float = field(default=1.0, metadata={"label": "Width Ratio"})
    height: float = field(default=1.0, metadata={"label": "Height Ratio"})

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

    def __post_init__(self) -> None:
        self.rotate = int(self.rotate)
        if self.rotate not in (0, 90, 180, 270):
            raise ValueError(
                f"Unsupported rotation angle: {self.rotate}. "
                f"Only 0/90/180/270/360 degrees supported."
            )


@dataclass
class MetadataConfig:
    """Metadata cleaning configuration model."""
    strip_all: bool = field(default=True, metadata={"label": "Strip All Metadata"})
    keep_icc: bool = field(default=True, metadata={"label": "Keep ICC Profile"})


@dataclass
class WatermarkConfig:
    """Text watermark configuration model."""
    text: str = field(default="", metadata={"label": "Text"})
    size: int = field(default=40, metadata={"label": "Font Size"})
    opacity: int = field(default=128, metadata={"label": "Opacity"})
    anchor: str = field(
        default="BR",
        metadata={"label": "Position", "options": ["TL", "TR", "BL", "BR", "C"]},
    )

    def __post_init__(self) -> None:
        if not isinstance(self.size, int) or self.size <= 0:
            raise ValueError("Font size must be a positive integer")
        if not isinstance(self.opacity, int) or not (0 <= self.opacity <= 255):
            raise ValueError("Opacity must be an integer between 0 and 255")
        valid_anchors = {"TL", "TR", "BL", "BR", "C"}
        if self.anchor not in valid_anchors:
            raise ValueError(
                f"Invalid anchor: {self.anchor}. "
                f"Valid options: {sorted(valid_anchors)}"
            )


@dataclass
class RoundedCornerConfig:
    """Rounded corner crop configuration model."""
    radius: int = field(default=20, metadata={"label": "Corner Radius (px)"})

    def __post_init__(self) -> None:
        if not isinstance(self.radius, int) or self.radius <= 0:
            raise ValueError("Radius must be a positive integer")


@dataclass
class BorderConfig:
    """Border/frame configuration model."""
    width: int = field(default=4, metadata={"label": "Border Width (px)"})
    color: str = field(default="#3b82f6", metadata={"label": "Color (hex)"})
    style: str = field(
        default="solid",
        metadata={"label": "Style", "options": ["solid", "dashed", "double"]},
    )

    def __post_init__(self) -> None:
        if not isinstance(self.width, int) or self.width <= 0:
            raise ValueError("Border width must be a positive integer")
        if not self.color.startswith("#") or len(self.color) not in (4, 7):
            raise ValueError("Color must be a hex string like #3b82f6")


@dataclass
class SmartCropConfig:
    """Content-aware crop configuration model."""
    threshold: int = field(
        default=30, metadata={"label": "Edge Threshold (0–255)"}
    )
    margin: int = field(default=10, metadata={"label": "Margin (px)"})

    def __post_init__(self) -> None:
        if not 0 <= self.threshold <= 255:
            raise ValueError("Threshold must be between 0 and 255")
        if not isinstance(self.margin, int) or self.margin < 0:
            raise ValueError("Margin must be a non-negative integer")
