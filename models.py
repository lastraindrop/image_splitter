# models.py
from dataclasses import dataclass, field
from typing import Tuple

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
            
        if any(o < 0 for o in self.offsets):
            raise ValueError("偏移量不能为负数")
            
        if not self.template or not isinstance(self.template, str):
            raise ValueError("命名模板不能为空")
