# image_splitter/processors/geometry.py
from typing import Any, Dict, List, Tuple

from PIL import Image

from image_splitter.engine.base import BaseProcessor
from image_splitter.models import GeometryConfig


class GeometryProcessor(BaseProcessor):
    """几何变换处理器。
    
    支持旋转（90/180/270度）以及水平/垂直翻转。
    """

    @property
    def config_model(self) -> type:
        return GeometryConfig

    @property
    def name(self) -> str:
        return "geometry"

    @property
    def display_name(self) -> str:
        return "几何变换 (Rotate & Flip)"

    @property
    def category(self) -> str:
        return "Transform"

    @property
    def tool_tip(self) -> str:
        return "对图像执行旋转或轴向翻转 (Rotate & Flip)。"

    def get_ui_metadata(self) -> List[Dict[str, Any]]:
        return [
            {"name": "rotate", "label": "旋转角度", "type": "int", "default": 0},
            {"name": "flip_h", "label": "水平翻转", "type": "bool", "default": False},
            {"name": "flip_v", "label": "垂直翻转", "type": "bool", "default": False}
        ]

    def process(
        self, 
        image: Image.Image, 
        config: Dict[str, Any]
    ) -> List[Tuple[Image.Image, Dict[str, Any]]]:
        """执行几何变换。"""
        angle = int(config.get("rotate", 0))
        fh = config.get("flip_h", False)
        fv = config.get("flip_v", False)

        img = image.copy()
        
        # 旋转
        if angle == 90:
            img = img.transpose(Image.ROTATE_90)
        elif angle == 180:
            img = img.transpose(Image.ROTATE_180)
        elif angle == 270:
            img = img.transpose(Image.ROTATE_270)
        
        # 翻转
        if fh:
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
        if fv:
            img = img.transpose(Image.FLIP_TOP_BOTTOM)

        return [(img, {"action": "geometry", "rotate": angle})]

    def draw_preview(self, canvas, thumb_size, canvas_pos, ratio, props, theme):
        try:
            def get_val(key):
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
