"""Canvas adjuster processor for padding or cropping image boundaries."""
# image_splitter/processors/adjuster.py
from typing import Any, Dict, List, Tuple

from PIL import Image

from image_splitter.engine.base import BaseProcessor
from image_splitter.models import AdjustConfig


class CanvasAdjuster(BaseProcessor):
    """Canvas adjuster processor.
    
    Adjusts canvas boundary by padding or cropping.
    """

    @property
    def config_model(self) -> type:
        return AdjustConfig

    @property
    def name(self) -> str:
        return "canvas_adjuster"

    @property
    def display_name(self) -> str:
        return "Canvas Adjuster"

    @property
    def category(self) -> str:
        return "Transform"

    @property
    def tool_tip(self) -> str:
        return "Adjust canvas boundary by padding or cropping."

    def get_ui_metadata(self) -> List[Dict[str, Any]]:
        return [
            {"name": "width", "label": "Target Width (ratio or px)", "type": "str", "default": "1.0"},
            {"name": "height", "label": "Target Height (ratio or px)", "type": "str", "default": "1.0"},
            {
                "name": "anchor", 
                "label": "Anchor", 
                "type": "enum", 
                "default": "center", 
                "options": ["center", "top-left", "top-right", "bottom-left", "bottom-right"]
            },
            {"name": "bg_color", "label": "Background RGBA", "type": "list", "default": [255, 255, 255, 255]}
        ]

    def process(
        self, 
        image: Image.Image, 
        config: Dict[str, Any]
    ) -> List[Tuple[Image.Image, Dict[str, Any]]]:
        """Perform canvas adjustment."""
        width = config.get("width", 1.0)
        height = config.get("height", 1.0)
        anchor = config.get("anchor", "center")
        bg_color = tuple(config.get("bg_color", [255, 255, 255, 255]))
        
        # Handle possible string input
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
