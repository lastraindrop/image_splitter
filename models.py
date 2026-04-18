# image_splitter/models.py
from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple


@dataclass
class SplitConfig:
    """网格切割配置模型。

    Attributes:
        rows: 切割行数。
        cols: 切割列数。
        output_dir: 结果输出目录。
        template: 输出文件名模板。
        offsets: 边缘偏移 (左, 上, 右, 下)。
    """
    rows: int
    cols: int
    output_dir: str
    template: str = "{filename}_{index}"
    offsets: Tuple[int, int, int, int] = (0, 0, 0, 0)

    def __post_init__(self):
        if not isinstance(self.rows, int) or not isinstance(self.cols, int):
            raise ValueError("行数和列数必须是整数")
        if not isinstance(self.offsets, (tuple, list)) or len(self.offsets) != 4:
            raise ValueError("偏移量必须为 4 个整数的元组或列表")
        self.validate()

    def validate(self):
        if self.rows <= 0 or self.cols <= 0:
            raise ValueError("行数和列数必须是正整数")
        if any(o < 0 for o in self.offsets):
            raise ValueError("偏移量不能为负数")


@dataclass
class AdjustConfig:
    """画布调整配置模型。"""
    width: Any
    height: Any
    output_dir: str
    anchor: str = "center"
    bg_color: Tuple[int, int, int, int] = (255, 255, 255, 255)
    template: str = "{filename}_adjusted"

    def __post_init__(self):
        if isinstance(self.width, str):
            self.width = float(self.width) if '.' in self.width else int(self.width)
        if isinstance(self.height, str):
            self.height = float(self.height) if '.' in self.height else int(self.height)
        self.validate()

    def validate(self):
        if not isinstance(self.width, (int, float)) or not isinstance(self.height, (int, float)):
            raise ValueError(f"目标宽高必须是数字 (Got {type(self.width)})")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("目标宽高必须大于 0")


@dataclass
class CustomSplitConfig:
    """自定义比例切割配置模型。"""
    h_lines: List[int]
    v_lines: List[int]
    output_dir: str
    template: str = "{filename}_{row}_{col}"

    def __post_init__(self):
        self.validate()

    def validate(self):
        if not isinstance(self.h_lines, (list, tuple)) or not isinstance(self.v_lines, (list, tuple)):
            raise ValueError("切割线必须是列表或元组格式")
        if any(not isinstance(x, int) or x < 0 for x in self.h_lines + self.v_lines):
            raise ValueError("切割线坐标必须是非负整数")


@dataclass
class ColorConfig:
    """色彩调节配置模型。"""
    brightness: float = 1.0
    contrast: float = 1.0
    sharpness: float = 1.0
    color: float = 1.0


@dataclass
class FilterConfig:
    """效果滤镜配置模型。"""
    grayscale: bool = False
    invert: bool = False


@dataclass
class FormatConfig:
    """格式转换配置模型。"""
    format: str = "WebP"
    quality: int = 80


@dataclass
class ResizeConfig:
    """图像缩放配置模型。"""
    width: float = 1.0
    height: float = 1.0

    def __post_init__(self):
        self.validate()

    def validate(self):
        if self.width <= 0 or self.height <= 0:
            raise ValueError("缩放比例必须大于 0")


@dataclass
class GeometryConfig:
    """几何变换配置模型。"""
    rotate: int = 0
    flip_h: bool = False
    flip_v: bool = False


@dataclass
class MetadataConfig:
    """元数据清理配置模型。"""
    strip_all: bool = True
    keep_icc: bool = True


@dataclass
class WatermarkConfig:
    """文字水印配置模型。"""
    text: str = ""
    size: int = 40
    opacity: int = 128
    anchor: str = "BR"
