# image_splitter/processors/resizer.py
from PIL import Image
from typing import List, Dict, Any, Tuple
from image_splitter.engine.base import BaseProcessor

class ImageResizer(BaseProcessor):
    """
    调整图片尺寸处理器
    """
    @property
    def name(self) -> str:
        return "resizer"

    @property
    def display_name(self) -> str:
        return "比例缩放 (Image Resizer)"

    @property
    def category(self) -> str:
        return "Transform"

    def get_ui_metadata(self) -> List[Dict[str, Any]]:
        return [
            {"name": "width", "label": "宽度比例", "type": "float", "default": 1.0},
            {"name": "height", "label": "高度比例", "type": "float", "default": 1.0}
        ]

    def process(self, image: Image.Image, config: Any) -> List[Tuple[Image.Image, Dict[str, Any]]]:
        if isinstance(config, dict):
            width = float(config.get("width", 1.0))
            height = float(config.get("height", 1.0))
        else:
            width, height = float(config.width), float(config.height)

        orig_w, orig_h = image.size
        # 如果是 float 则视为比例，int 则视为绝对像素 (在这里我们统一处理为比例，或者根据输入类型判断)
        # 为了简单，我们目前仅支持比例
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
