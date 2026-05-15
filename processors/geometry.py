"""Geometry transformation processor for image rotation and flipping."""
# image_splitter/processors/geometry.py
from typing import Any, Dict, List, Tuple

from PIL import Image

from image_splitter.engine.base import BaseProcessor
from image_splitter.models import GeometryConfig


class GeometryProcessor(BaseProcessor):
    """Geometry transformation processor.
    
    Supports rotation (90/180/270 degrees) and horizontal/vertical flipping.
    """

    @property
    def config_model(self) -> type:
        return GeometryConfig

    @property
    def name(self) -> str:
        return "geometry"

    @property
    def display_name(self) -> str:
        return "Rotate & Flip"

    @property
    def category(self) -> str:
        return "Transform"

    @property
    def tool_tip(self) -> str:
        return "Rotate or flip image horizontally or vertically."

    def get_ui_metadata(self) -> List[Dict[str, Any]]:
        return [
            {"name": "rotate", "label": "Rotate", "type": "enum", "default": "0", "options": ["0", "90", "180", "270"]},
            {"name": "flip_h", "label": "Flip Horizontal", "type": "bool", "default": False},
            {"name": "flip_v", "label": "Flip Vertical", "type": "bool", "default": False}
        ]

    def process(
        self,
        image: Image.Image,
        config: Dict[str, Any]
    ) -> List[Tuple[Image.Image, Dict[str, Any]]]:
        """Perform geometry transform."""
        angle = int(config.get("rotate", 0))
        fh = config.get("flip_h", False)
        fv = config.get("flip_v", False)

        # Validate angle
        if angle not in (0, 90, 180, 270, 360):
            raise ValueError(f"Unsupported rotation angle: {angle}. Only 0/90/180/270 degrees supported.")

        img = image.copy()

        # Rotation
        if angle == 90:
            img = img.transpose(Image.Transpose.ROTATE_90)
        elif angle == 180:
            img = img.transpose(Image.Transpose.ROTATE_180)
        elif angle == 270:
            img = img.transpose(Image.Transpose.ROTATE_270)

        # Flipping
        if fh:
            img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        if fv:
            img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        return [(img, {"action": "geometry", "rotate": angle})]

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
            def get_val(key: str) -> Any:
                v = props.get(key)
                return v.get() if hasattr(v, 'get') else v

            angle = int(get_val("rotate") or 0)
            if angle == 0:
                return
            
            cw, ch = thumb_size
            x0, y0 = canvas_pos
            cx, cy = x0 + cw // 2, y0 + ch // 2
            
            canvas.create_oval(
                cx - 20, cy - 20, cx + 20, cy + 20, 
                outline=theme.PRIMARY, width=2, tags="overlay"
            )
            canvas.create_text(
                cx, cy, text=f"{angle}°", 
                fill=theme.PRIMARY, font=("Arial", 10, "bold"), tags="overlay"
            )
        except Exception:
            pass
