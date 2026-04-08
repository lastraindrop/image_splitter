# image_splitter/processors/custom_splitter.py
import ast
from PIL import Image
from typing import List, Dict, Any, Tuple
from image_splitter.engine.base import BaseProcessor
from image_splitter.models import CustomSplitConfig

class CustomLineSplitter(BaseProcessor):
    """
    基于自定义坐标线的切割处理器
    """
    @property
    def name(self) -> str:
        return "custom_splitter"

    @property
    def display_name(self) -> str:
        return "比例切割 (Custom Lines)"

    @property
    def category(self) -> str:
        return "Split"

    def get_ui_metadata(self) -> List[Dict[str, Any]]:
        return [
            {"name": "h_lines", "label": "横向切割线", "type": "list", "default": [50]},
            {"name": "v_lines", "label": "纵向切割线", "type": "list", "default": [50]}
        ]

    def process(self, image: Image.Image, config: Any) -> List[Tuple[Image.Image, Dict[str, Any]]]:
        if isinstance(config, dict):
            h_lines = config.get("h_lines", [])
            v_lines = config.get("v_lines", [])
            if isinstance(h_lines, str): h_lines = ast.literal_eval(h_lines)
            if isinstance(v_lines, str): v_lines = ast.literal_eval(v_lines)
        else:
            h_lines, v_lines = config.h_lines, config.v_lines

        w, h = image.size
        # 生成边界点并去重排序: [0, y1, y2, ..., h]
        y_points = sorted(list(set([0, h] + [y for y in h_lines if 0 < y < h])))
        x_points = sorted(list(set([0, w] + [x for x in v_lines if 0 < x < w])))
        
        results = []
        count = 1
        for i in range(len(y_points) - 1):
            for j in range(len(x_points) - 1):
                left, upper = x_points[j], y_points[i]
                right, lower = x_points[j+1], y_points[i+1]
                
                cell = image.crop((left, upper, right, lower))
                context = {
                    "row": i + 1,
                    "col": j + 1,
                    "index": str(count).zfill(2)
                }
                results.append((cell, context))
                count += 1
                
        return results

    def draw_preview(self, canvas, thumb_size, canvas_pos, ratio, props, theme):
        try:
            raw_h = props.get("h_lines").get()
            raw_v = props.get("v_lines").get()
            h_lines = ast.literal_eval(raw_h) if isinstance(raw_h, str) else raw_h
            v_lines = ast.literal_eval(raw_v) if isinstance(raw_v, str) else raw_v

            cw, ch = thumb_size
            x0, y0 = canvas_pos

            for line in h_lines:
                y = y0 + int(int(line) * ratio)
                if y0 < y < y0 + ch:
                    canvas.create_line(x0, y, x0 + cw, y, fill=theme.INFO, dash=(4, 4), tags="overlay")
            for line in v_lines:
                x = x0 + int(int(line) * ratio)
                if x0 < x < x0 + cw:
                    canvas.create_line(x, y0, x, y0 + ch, fill=theme.INFO, dash=(4, 4), tags="overlay")
        except Exception:
            pass
