"""Grid splitter processor for dividing images into uniform tiles."""
import ast
from typing import Any, Dict, List, Tuple

from PIL import Image

from image_splitter.engine.base import BaseProcessor
from image_splitter.models import SplitConfig


class GridSplitter(BaseProcessor):
    """Grid splitter processor.
    
    Splits image into rows x cols grid with optional edge offsets.
    """

    @property
    def config_model(self) -> type:
        return SplitConfig

    @property
    def name(self) -> str:
        return "grid_splitter"

    @property
    def display_name(self) -> str:
        return "Grid Splitter"

    @property
    def category(self) -> str:
        return "Split"

    @property
    def tool_tip(self) -> str:
        return "Split image into rows x cols grid with optional edge offsets to exclude borders."

    def get_ui_metadata(self) -> List[Dict[str, Any]]:
        return [
            {"name": "rows", "label": "Rows", "type": "int", "default": 3},
            {"name": "cols", "label": "Cols", "type": "int", "default": 3},
            {"name": "offsets", "label": "Offsets (L,T,R,B)", "type": "list", "default": [0, 0, 0, 0]}
        ]

    def process(
        self, 
        image: Image.Image, 
        config: Dict[str, Any]
    ) -> List[Tuple[Image.Image, Dict[str, Any]]]:
        """Perform grid split."""
        rows = config.get("rows", 1)
        cols = config.get("cols", 1)
        offsets = config.get("offsets", [0, 0, 0, 0])

        # 1. Apply offsets
        orig_w, orig_h = image.size
        l_off, t_off, r_off, b_off = offsets
        crop_box = (l_off, t_off, orig_w - r_off, orig_h - b_off)
        
        # 2. Pre-validation
        if crop_box[2] <= crop_box[0] or crop_box[3] <= crop_box[1]:
            raise ValueError(f"Offsets result in invalid region: {crop_box}")
            
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

    def draw_preview(
        self,
        canvas: Any,
        thumb_size: Tuple[int, int],
        canvas_pos: Tuple[int, int],
        ratio: float,
        props: Dict[str, Any],
        theme: Any
    ) -> None:
        try:
            def get_val(key, default=0):
                v = props.get(key)
                val = v.get().strip() if v is not None else ""
                try: 
                    return ast.literal_eval(val) if val else default
                except Exception: 
                    return default

            rows = max(1, int(get_val("rows", 1)))
            cols = max(1, int(get_val("cols", 1)))
            offsets = get_val("offsets", (0, 0, 0, 0))
            
            cw, ch = thumb_size
            x0, y0 = canvas_pos
            
            cx1, cy1 = x0 + int(offsets[0] * ratio), y0 + int(offsets[1] * ratio)
            cx2, cy2 = x0 + cw - int(offsets[2] * ratio), y0 + ch - int(offsets[3] * ratio)
            
            if cx2 > cx1 and cy2 > cy1:
                canvas.create_rectangle(
                    cx1, cy1, cx2, cy2, 
                    outline=theme.ACCENT, width=2, dash=(4, 4), tags="overlay"
                )
                for i in range(1, rows):
                    y = cy1 + (cy2 - cy1) * i / rows
                    canvas.create_line(cx1, y, cx2, y, fill=theme.INFO, tags="overlay")
                for j in range(1, cols):
                    x = cx1 + (cx2 - cx1) * j / cols
                    canvas.create_line(x, cy1, x, cy2, fill=theme.INFO, tags="overlay")
        except Exception:
            pass
