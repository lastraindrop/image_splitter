# image_splitter/processors/filters.py
from typing import Any, Dict, List, Tuple

from PIL import Image, ImageOps

from image_splitter.engine.base import BaseProcessor
from image_splitter.models import FilterConfig


class SimpleFilterProcessor(BaseProcessor):
    """轻量级效果滤镜。
    
    支持极速的灰度化和反色处理。
    """

    @property
    def config_model(self) -> type:
        return FilterConfig

    @property
    def name(self) -> str:
        return "filters"

    @property
    def display_name(self) -> str:
        return "效果滤镜 (Effects)"

    @property
    def category(self) -> str:
        return "Filter"

    @property
    def tool_tip(self) -> str:
        return "提供极速的像素级滤镜：灰度化或反色处理。"

    def get_ui_metadata(self) -> List[Dict[str, Any]]:
        return [
            {"name": "grayscale", "label": "灰度化", "type": "bool", "default": False},
            {"name": "invert", "label": "反色/底片", "type": "bool", "default": False}
        ]

    def process(
        self, 
        image: Image.Image, 
        config: Dict[str, Any]
    ) -> List[Tuple[Image.Image, Dict[str, Any]]]:
        """执行滤镜处理。"""
        gs = config.get("grayscale", False)
        inv = config.get("invert", False)

        img = image.copy()
        
        if gs:
            img = img.convert("L").convert("RGB")
        
        if inv:
            if img.mode == 'RGBA':
                r, g, b, a = img.split()
                rgb = Image.merge('RGB', (r, g, b))
                inv_rgb = ImageOps.invert(rgb)
                r, g, b = inv_rgb.split()
                img = Image.merge('RGBA', (r, g, b, a))
            else:
                img = ImageOps.invert(img)

        return [(img, {"action": "filter"})]

    def draw_preview(self, canvas, thumb_size, canvas_pos, ratio, props, theme):
        try:
            def get_val(key):
                v = props.get(key)
                return v.get() if hasattr(v, 'get') else v

            gs = get_val("grayscale")
            inv = get_val("invert")
            if not gs and not inv:
                return
            
            x0, y0 = canvas_pos
            canvas.create_text(
                x0 + 10, y0 + 10, 
                text="[FX Active]", 
                fill=theme.SUCCESS, 
                anchor="nw", 
                font=("Arial", 8), 
                tags="overlay"
            )
        except Exception:
            pass
