# image_splitter/models.py
from dataclasses import dataclass, field
from typing import Tuple, List, Optional
import os

@dataclass
class SplitConfig:
    """网格切割配置类"""
    rows: int
    cols: int
    output_dir: str
    template: str = "{filename}_{index}"
    offsets: Tuple[int, int, int, int] = (0, 0, 0, 0) # 左, 上, 右, 下

    def __post_init__(self):
        # 严格类型校验
        if not isinstance(self.rows, int) or not isinstance(self.cols, int):
             raise ValueError("行数和列数必须是整数")
        if not isinstance(self.offsets, (tuple, list)) or len(self.offsets) != 4:
             raise ValueError("偏移量必须为4个整数的元组或列表")
        if not all(isinstance(o, int) for o in self.offsets):
             raise ValueError("偏移量所有元素必须为整数")
        self.validate()

    def validate(self):
        if self.rows <= 0 or self.cols <= 0:
            raise ValueError("行数和列数必须是正整数")
        if not self.output_dir:
            raise ValueError("输出目录路径不能为空")
        if any(o < 0 for o in self.offsets):
            raise ValueError("偏移量不能为负数")

@dataclass
class AdjustConfig:
    """画布调整配置类"""
    width: float # 比例或绝对像素
    height: float
    output_dir: str
    anchor: str = "center"
    bg_color: Tuple[int, int, int, int] = (255, 255, 255, 255)
    template: str = "{filename}_adjusted"

    def __post_init__(self):
        self.validate()

    def validate(self):
        if not isinstance(self.width, (int, float)) or not isinstance(self.height, (int, float)):
            raise ValueError("目标宽高必须是数字")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("目标宽高必须大于0")
        if not self.output_dir:
            raise ValueError("输出目录路径不能为空")

@dataclass
class CustomSplitConfig:
    """自定义比例切割配置类"""
    h_lines: List[int]
    v_lines: List[int]
    output_dir: str
    template: str = "{filename}_{row}_{col}"

    def __post_init__(self):
        self.validate()

    def validate(self):
        if not isinstance(self.h_lines, list) or not isinstance(self.v_lines, list):
             raise ValueError("切割线必须是列表格式")
        if any(not isinstance(x, int) or x < 0 for x in self.h_lines):
             raise ValueError("横向切割线坐标必须是非负整数")
        if any(not isinstance(x, int) or x < 0 for x in self.v_lines):
             raise ValueError("纵向切割线坐标必须是非负整数")
        if not self.output_dir:
             raise ValueError("输出目录路径不能为空")
