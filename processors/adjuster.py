# image_splitter/processors/adjuster.py
from PIL import Image
from typing import List, Dict, Any, Tuple
from image_splitter.engine.base import BaseProcessor
from image_splitter.models import AdjustConfig

class CanvasAdjuster(BaseProcessor):
    """
    画布调整处理器：增添/裁剪/填充
    """
    @property
    def name(self) -> str:
        return "canvas_adjuster"

    @property
    def display_name(self) -> str:
        return "画布调整 (Canvas Adjuster)"

    @property
    def category(self) -> str:
        return "Transform"

    def get_ui_metadata(self) -> List[Dict[str, Any]]:
        return [
            {"name": "width", "label": "目标宽度 (比例或像素)", "type": "str", "default": "1.0"},
            {"name": "height", "label": "目标高度 (比例或像素)", "type": "str", "default": "1.0"},
            {"name": "anchor", "label": "锚点", "type": "enum", "default": "center", "options": ["center", "top-left", "top-right", "bottom-left", "bottom-right"]},
            {"name": "bg_color", "label": "背景色 RGBA", "type": "str", "default": "(255, 255, 255, 255)"}
        ]

    def process(self, image: Image.Image, config: Any) -> List[Tuple[Image.Image, Dict[str, Any]]]:
        import ast
        
        if isinstance(config, dict):
            width = config.get("width", 1.0)
            height = config.get("height", 1.0)
            anchor = config.get("anchor", "center")
            bg_color = config.get("bg_color", "(255, 255, 255, 255)")
            
            if isinstance(width, str): width = float(width) if '.' in width else int(width)
            if isinstance(height, str): height = float(height) if '.' in height else int(height)
            if isinstance(bg_color, str): bg_color = ast.literal_eval(bg_color)
        else:
            width, height, anchor, bg_color = config.width, config.height, config.anchor, config.bg_color

        orig_w, orig_h = image.size
        target_w = int(orig_w * width) if isinstance(width, float) else int(width)
        target_h = int(orig_h * height) if isinstance(height, float) else int(height)
        if target_w <= 0 or target_h <= 0:
            raise ValueError("目标宽高必须大于 0")
        
        mode = "RGBA" if "A" in image.mode or len(bg_color) > 3 else "RGB"
        new_img = Image.new(mode, (target_w, target_h), bg_color)
        
        paste_x, paste_y = 0, 0
        if anchor == "center":
            paste_x = (target_w - orig_w) // 2
            paste_y = (target_h - orig_h) // 2
        elif anchor == "top-left":
            paste_x, paste_y = 0, 0
        elif anchor == "top-right":
            paste_x = target_w - orig_w
            paste_y = 0
        elif anchor == "bottom-left":
            paste_x = 0
            paste_y = target_h - orig_h
        elif anchor == "bottom-right":
            paste_x = target_w - orig_w
            paste_y = target_h - orig_h
            
        if mode == "RGBA":
            temp_img = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
            temp_img.paste(image, (paste_x, paste_y))
            new_img = Image.alpha_composite(new_img.convert("RGBA"), temp_img)
        else:
            new_img.paste(image, (paste_x, paste_y))
            
        context = {
            "action": "adjusted",
            "orig_w": orig_w,
            "orig_h": orig_h,
            "target_w": target_w,
            "target_h": target_h,
            "anchor": anchor
        }
        
        return [(new_img, context)]
