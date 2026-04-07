# image_splitter/processors/filters.py
from PIL import Image, ImageOps
from typing import List, Dict, Any, Tuple
from image_splitter.engine.base import BaseProcessor

class SimpleFilterProcessor(BaseProcessor):
    """
    轻量级滤镜：灰度、反色
    """
    @property
    def name(self) -> str:
        return "filters"

    @property
    def display_name(self) -> str:
        return "效果滤镜 (Effects)"

    @property
    def category(self) -> str:
        return "Filter"

    def get_ui_metadata(self) -> List[Dict[str, Any]]:
        return [
            {"name": "grayscale", "label": "灰度化 (True/False)", "type": "bool", "default": False},
            {"name": "invert", "label": "反色/底片 (True/False)", "type": "bool", "default": False}
        ]

    def process(self, image: Image.Image, config: Any) -> List[Tuple[Image.Image, Dict[str, Any]]]:
        gs = config.get("grayscale", False) if isinstance(config, dict) else getattr(config, 'grayscale', False)
        inv = config.get("invert", False) if isinstance(config, dict) else getattr(config, 'invert', False)

        img = image.copy()
        
        if str(gs).lower() == "true":
            # 转换为 8 位灰度
            img = img.convert("L").convert("RGB")
        
        if str(inv).lower() == "true":
            # 兼容 RGBA (透明通道不应反转)
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
        # 滤镜效果通常在预览中通过 overlay 很难完全模拟
        # 暂时只画一个状态提示
        try:
            gs = props.get("grayscale").get() or "False"
            inv = props.get("invert").get() or "False"
            if gs == "False" and inv == "False": return
            
            cw, ch = thumb_size
            x0, y0 = canvas_pos
            
            canvas.create_text(x0 + 10, y0 + 10, text="[FX Active]", fill=theme.SUCCESS, anchor="nw", font=("Arial", 8), tags="overlay")
        except: pass
