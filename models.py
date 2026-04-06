# models.py
from dataclasses import dataclass, field
from typing import Tuple, List, Any

@dataclass
class AdjustConfig:
    """
    画布调整配置 (增添/裁剪/填充)
    """
    width: Any  # int (px) 或 float (ratio)
    height: Any # int (px) 或 float (ratio)
    anchor: str = "center"  # center, top-left, top-right, bottom-left, bottom-right
    bg_color: Tuple[int, ...] = (255, 255, 255, 255) # 默认白色
    output_dir: str = "./output"
    template: str = "{filename}_adjusted"

    def validate(self):
        if not self.output_dir:
            raise ValueError("输出目录不能为空")
        if not self.width or not self.height:
            raise ValueError("宽高必须指定且大于0")

@dataclass
class CustomSplitConfig:
    """
    自定义线条切割配置
    """
    h_lines: List[int]  # 横向切割线的 Y 坐标
    v_lines: List[int]  # 纵向切割线的 X 坐标
    output_dir: str
    template: str = "{filename}_{row}_{col}"
    offsets: Tuple[int, int, int, int] = (0, 0, 0, 0)

    def validate(self):
        if not self.output_dir:
            raise ValueError("输出目录不能为空")
        # 允许负数或大数，在处理器中会被过滤，不在这里抛异常，
        # 除非我们要强制要求输入合法。
        pass

@dataclass
class SplitConfig:
    """
    切割配置数据模型，包含参数校验逻辑
    """
    rows: int
    cols: int
    output_dir: str
    template: str = "{filename}_{index}"
    offsets: Tuple[int, int, int, int] = (0, 0, 0, 0)

    def __post_init__(self):
        # Fail-Fast 校验逻辑
        if self.rows <= 0 or self.cols <= 0:
            raise ValueError("行数和列数必须大于0")
            
        if not self.output_dir or not isinstance(self.output_dir, str):
            raise ValueError("输出目录路径不能为空且必须是字符串")

        if len(self.offsets) != 4:
            raise ValueError("偏移量必须为4个整数 (左, 上, 右, 下)")
        try:
            self.offsets = tuple(int(o) for o in self.offsets)
        except (ValueError, TypeError):
            raise ValueError("偏移量所有元素必须为有效的整数")

        if any(o < 0 for o in self.offsets):
            raise ValueError("偏移量不能为负数")
            
        if not self.template or not isinstance(self.template, str):
            raise ValueError("命名模板不能为空")
