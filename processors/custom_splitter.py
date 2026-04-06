# image_splitter/processors/custom_splitter.py
from PIL import Image
from typing import List, Dict, Any, Tuple
from engine.base import BaseProcessor
from models import CustomSplitConfig

class CustomLineSplitter(BaseProcessor):
    """
    自定义线条切割处理器插件
    """
    @property
    def name(self) -> str:
        return "custom_splitter"

    @property
    def display_name(self) -> str:
        return "自定义线切割 (Custom Splitter)"

    def process(self, image: Image.Image, config: CustomSplitConfig) -> List[Tuple[Image.Image, Dict[str, Any]]]:
        # 1. 应用偏移量
        orig_w, orig_h = image.size
        l_off, t_off, r_off, b_off = config.offsets
        img = image.crop((l_off, t_off, orig_w - r_off, orig_h - b_off))
        w, h = img.size

        # 2. 准备坐标轴并排序
        # 过滤掉超出图片范围的线，并加入边界 [0, ..., max]
        y_coords = sorted(list(set([0, h] + [y for y in config.h_lines if 0 < y < h])))
        x_coords = sorted(list(set([0, w] + [x for x in config.v_lines if 0 < x < w])))

        results = []
        count = 1
        
        # 3. 嵌套循环切割
        # Y 轴区间 (行)
        for i in range(len(y_coords) - 1):
            y_start, y_end = y_coords[i], y_coords[i+1]
            
            # X 轴区间 (列)
            for j in range(len(x_coords) - 1):
                x_start, x_end = x_coords[j], x_coords[j+1]
                
                # 执行裁剪
                cell = img.crop((x_start, y_start, x_end, y_end))
                
                context = {
                    "row": i + 1,
                    "col": j + 1,
                    "index": str(count).zfill(2),
                    "x_start": x_start,
                    "y_start": y_start,
                    "width": x_end - x_start,
                    "height": y_end - y_start
                }
                
                results.append((cell, context))
                count += 1
                
        return results
