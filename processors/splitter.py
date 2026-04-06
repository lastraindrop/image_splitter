# image_splitter/processors/splitter.py
import ast
from PIL import Image
from typing import List, Dict, Any, Tuple
from image_splitter.engine.base import BaseProcessor

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

    @property
    def category(self) -> str:
        return "Split"

    def get_ui_metadata(self) -> List[Dict[str, Any]]:
        return [
            {"name": "rows", "label": "行数", "type": "int", "default": 3},
            {"name": "cols", "label": "列数", "type": "int", "default": 3},
            {"name": "offsets", "label": "偏移 (L,T,R,B)", "type": "str", "default": "(0,0,0,0)"}
        ]

    def process(self, image: Image.Image, config: Any) -> List[Tuple[Image.Image, Dict[str, Any]]]:
        if isinstance(config, dict):
            rows = int(config.get("rows", 1))
            cols = int(config.get("cols", 1))
            off_val = config.get("offsets", (0, 0, 0, 0))
            if isinstance(off_val, str):
                 try:
                    offsets = ast.literal_eval(off_val)
                 except:
                    raise ValueError(f"无法解析偏移量字符串: {off_val}")
            else:
                offsets = off_val
        else:
            rows = int(config.rows)
            cols = int(config.cols)
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
            def get_val(key, default=0):
                val = props.get(key).get().strip()
                try: return ast.literal_eval(val) if val else default
                except: return default

            rows = max(1, int(get_val("rows", 1)))
            cols = max(1, int(get_val("cols", 1)))
            offsets = get_val("offsets", (0, 0, 0, 0))
            
            cw, ch = thumb_size
            x0, y0 = canvas_pos
            
            cx1, cy1 = x0 + int(offsets[0] * ratio), y0 + int(offsets[1] * ratio)
            cx2, cy2 = x0 + cw - int(offsets[2] * ratio), y0 + ch - int(offsets[3] * ratio)
            
            if cx2 > cx1 and cy2 > cy1:
                canvas.create_rectangle(cx1, cy1, cx2, cy2, outline=theme.ACCENT, width=2, dash=(4,4), tags="overlay")
                for i in range(1, rows):
                    y = cy1 + (cy2 - cy1) * i / rows
                    canvas.create_line(cx1, y, cx2, y, fill=theme.INFO, tags="overlay")
                for j in range(1, cols):
                    x = cx1 + (cx2 - cx1) * j / cols
                    canvas.create_line(x, cy1, x, cy2, fill=theme.INFO, tags="overlay")
        except:
            pass
