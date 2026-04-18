# image_splitter/processors/resizer.py
from typing import Any, Dict, List, Tuple

from PIL import Image

from image_splitter.engine.base import BaseProcessor
from image_splitter.models import ResizeConfig


class ImageResizer(BaseProcessor):
    """Image resizer processor.

    Scales image dimensions by ratio using LANCZOS algorithm.
    """

    @property
    def config_model(self) -> type:
        return ResizeConfig

    @property
    def name(self) -> str:
        return "resizer"

    @property
    def display_name(self) -> str:
        return "Image Resizer"

    @property
    def category(self) -> str:
        return "Transform"

    @property
    def tool_tip(self) -> str:
        return "Scale image dimensions by ratio using LANCZOS algorithm."

    def get_ui_metadata(self) -> List[Dict[str, Any]]:
        return [
            {"name": "width", "label": "Width Ratio", "type": "float", "default": 1.0},
            {"name": "height", "label": "Height Ratio", "type": "float", "default": 1.0}
        ]

    def process(
        self, 
        image: Image.Image, 
        config: Dict[str, Any]
    ) -> List[Tuple[Image.Image, Dict[str, Any]]]:
        """Perform image resize."""
        width = float(config.get("width", 1.0))
        height = float(config.get("height", 1.0))

        orig_w, orig_h = image.size
        target_w = int(orig_w * width)
        target_h = int(orig_h * height)
        if target_w <= 0 or target_h <= 0:
            raise ValueError("目标宽高必须大于 0")
        
        new_img = image.resize((target_w, target_h), Image.Resampling.LANCZOS)
        
        context = {
            "action": "resized",
            "orig_w": orig_w,
            "orig_h": orig_h,
            "target_w": target_w,
            "target_h": target_h
        }
        
        return [(new_img, context)]
