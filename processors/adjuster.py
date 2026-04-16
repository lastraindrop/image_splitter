# image_splitter/processors/adjuster.py
from typing import Any, Dict, List, Tuple

from PIL import Image

from image_splitter.engine.base import BaseProcessor
from image_splitter.models import AdjustConfig


class CanvasAdjuster(BaseProcessor):
    """画布调整处理器。
    
    支持调整画布边界，包括扩充（Padding）或裁剪（Cropping）。
    """

    @property
    def config_model(self) -> type:
        return AdjustConfig

    @property
    def name(self) -> str:
        return "canvas_adjuster"

    @property
    def display_name(self) -> str:
        return "画布调整 (Canvas Adjuster)"

    @property
    def category(self) -> str:
        return "Transform"

    @property
    def tool_tip(self) -> str:
        return "调整画布的边界，支持扩充或裁剪 (Canvas Adjuster)。"

    def get_ui_metadata(self) -> List[Dict[str, Any]]:
        return [
            {"name": "width", "label": "目标宽度 (比例或像素)", "type": "str", "default": "1.0"},
            {"name": "height", "label": "目标高度 (比例或像素)", "type": "str", "default": "1.0"},
            {
                "name": "anchor", 
                "label": "锚点", 
                "type": "enum", 
                "default": "center", 
                "options": ["center", "top-left", "top-right", "bottom-left", "bottom-right"]
            },
            {"name": "bg_color", "label": "背景色 RGBA", "type": "list", "default": [255, 255, 255, 255]}
        ]

    def process(
        self, 
        image: Image.Image, 
        config: Dict[str, Any]
    ) -> List[Tuple[Image.Image, Dict[str, Any]]]:
        """执行画布调整。"""
        width = config.get("width", 1.0)
        height = config.get("height", 1.0)
        anchor = config.get("anchor", "center")
        bg_color = tuple(config.get("bg_color", [255, 255, 255, 255]))
        
        # 处理可能的字符串输入
        if isinstance(width, str):
            width = float(width) if '.' in width else int(width)
        if isinstance(height, str):
            height = float(height) if '.' in height else int(height)

        orig_w, orig_h = image.size
        target_w = int(orig_w * width) if isinstance(width, float) else int(width)
        target_h = int(orig_h * height) if isinstance(height, float) else int(height)
        
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
