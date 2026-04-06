# image_splitter/processors/splitter.py
from PIL import Image
from typing import List, Dict, Any, Tuple
from engine.base import BaseProcessor
from models import SplitConfig

class GridSplitter(BaseProcessor):
    """
    网格切割处理器插件 (高性能实现)
    """
    @property
    def name(self) -> str:
        return "grid_splitter"

    @property
    def display_name(self) -> str:
        return "网格切割 (Grid Splitter)"

    def get_ui_metadata(self) -> List[Dict[str, Any]]:
        return [
            {"name": "rows", "label": "行数", "type": "int", "default": 3},
            {"name": "cols", "label": "列数", "type": "int", "default": 3},
            {"name": "offsets", "label": "偏移 (L,T,R,B)", "type": "str", "default": "(0,0,0,0)"}
        ]

    def process(self, image: Image.Image, config: Any) -> List[Tuple[Image.Image, Dict[str, Any]]]:
        """
        支持配置类或简单的参数字典
        """
        # 允许通过字典传参 (例如从 CLI 解析出来的 props)
        if isinstance(config, dict):
            rows = config.get("rows", 1)
            cols = config.get("cols", 1)
            offsets = config.get("offsets", (0, 0, 0, 0))
            if isinstance(offsets, str):
                # 尝试解析 [0,0,0,0] 格式
                offsets = eval(offsets)
        else:
            rows = config.rows
            cols = config.cols
            offsets = config.offsets

        # 1. 应用偏移量
        orig_w, orig_h = image.size
        l_off, t_off, r_off, b_off = offsets
        crop_box = (l_off, t_off, orig_w - r_off, orig_h - b_off)
        
        # 2. 预校验
        if crop_box[2] <= crop_box[0] or crop_box[3] <= crop_box[1]:
            raise ValueError(f"偏移量导致区域无效: {crop_box}")
            
        img = image.crop(crop_box)
        img_width, img_height = img.size
        
        results = []
        count = 1
        for i in range(rows):
            for j in range(cols):
                left = (j * img_width) // cols
                upper = (i * img_height) // rows
                right = ((j + 1) * img_width) // cols
                lower = ((i + 1) * img_height) // rows
                
                if right <= left or lower <= upper:
                    continue
                    
                cell = img.crop((left, upper, right, lower))
                
                # 为模板渲染提供的上下文
                context = {
                    "row": i + 1,
                    "col": j + 1,
                    "index": str(count).zfill(2)
                }
                results.append((cell, context))
                count += 1
                
        return results
