"""Custom line splitter processor for dividing images at specific pixel coordinates."""
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

    def draw_preview(
        self,
        canvas: Any,
        thumb_size: Tuple[int, int],
        canvas_pos: Tuple[int, int],
        ratio: float,
        props: Dict[str, Any],
        theme: Any
    ) -> None:
        """Draw guide lines with handles for interactive dragging.

        Each line is tagged ``guide_h_N`` or ``guide_v_N`` so the GUI
        can detect clicks and enable drag-to-adjust.  Small square
        handles at line endpoints serve as visible drag affordances.
        """
        try:
            def get_val(key: str) -> Any:
                v = props.get(key)
                if v is None:
                    return None
                return v.get() if hasattr(v, 'get') else v

            h_lines = get_val("h_lines")
            v_lines = get_val("v_lines")
            if isinstance(h_lines, str):
                h_lines = ast.literal_eval(h_lines)
            if isinstance(v_lines, str):
                v_lines = ast.literal_eval(v_lines)

            if not isinstance(h_lines, list):
                h_lines = []
            if not isinstance(v_lines, list):
                v_lines = []

            cw, ch = thumb_size
            x0, y0 = canvas_pos
            line_color = getattr(theme, "ACCENT", "#3b82f6")
            handle_size = 6

            for i, line in enumerate(h_lines):
                y = y0 + int(int(line) * ratio)
                if y0 < y < y0 + ch:
                    tag = f"guide_h_{i}"
                    canvas.create_line(
                        x0, y, x0 + cw, y,
                        fill=line_color, dash=(4, 4), width=2,
                        tags=("overlay", "guide_line", tag),
                    )
                    # Drag handle on left side
                    canvas.create_rectangle(
                        x0 - handle_size, y - handle_size,
                        x0 + handle_size, y + handle_size,
                        fill=line_color, outline="",
                        tags=("overlay", "guide_line", tag, "guide_handle"),
                    )
            for j, line in enumerate(v_lines):
                x = x0 + int(int(line) * ratio)
                if x0 < x < x0 + cw:
                    tag = f"guide_v_{j}"
                    canvas.create_line(
                        x, y0, x, y0 + ch,
                        fill=line_color, dash=(4, 4), width=2,
                        tags=("overlay", "guide_line", tag),
                    )
                    # Drag handle on top
                    canvas.create_rectangle(
                        x - handle_size, y0 - handle_size,
                        x + handle_size, y0 + handle_size,
                        fill=line_color, outline="",
                        tags=("overlay", "guide_line", tag, "guide_handle"),
                    )
        except Exception:
            import logging
            logging.getLogger(__name__).debug(
                "draw_preview failed", exc_info=True
            )
