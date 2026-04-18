# image_splitter/processors/custom_splitter.py
import ast
from typing import Any, Dict, List, Tuple

from PIL import Image

from image_splitter.engine.base import BaseProcessor
from image_splitter.models import CustomSplitConfig


class CustomLineSplitter(BaseProcessor):
    """Custom line splitter processor.
    
    Splits image using custom horizontal or vertical cut lines at specified pixel positions.
    """

    @property
    def config_model(self) -> type:
        return CustomSplitConfig

    @property
    def name(self) -> str:
        return "custom_splitter"

    @property
    def display_name(self) -> str:
        return "Custom Lines"

    @property
    def category(self) -> str:
        return "Split"

    @property
    def tool_tip(self) -> str:
        return "Add horizontal or vertical cut lines at specified pixel positions."

    def get_ui_metadata(self) -> List[Dict[str, Any]]:
        return [
            {"name": "h_lines", "label": "Horizontal Lines", "type": "list", "default": [50]},
            {"name": "v_lines", "label": "Vertical Lines", "type": "list", "default": [50]}
        ]

    def process(
        self, 
        image: Image.Image, 
        config: Dict[str, Any]
    ) -> List[Tuple[Image.Image, Dict[str, Any]]]:
        """Perform custom line split."""
        h_lines = config.get("h_lines", [])
        v_lines = config.get("v_lines", [])

        w, h = image.size
        # Generate boundary points and dedupe
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
            def get_val(key):
                v = props.get(key)
                return v.get() if hasattr(v, 'get') else v

            h_lines = get_val("h_lines")
            v_lines = get_val("v_lines")
            if isinstance(h_lines, str):
                h_lines = ast.literal_eval(h_lines)
            if isinstance(v_lines, str):
                v_lines = ast.literal_eval(v_lines)

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
