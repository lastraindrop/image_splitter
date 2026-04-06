# image_splitter/processors/resizer.py
from PIL import Image
from typing import List, Dict, Any, Tuple
from engine.base import BaseProcessor, BaseConfig
from dataclasses import dataclass

@dataclass
class ResizeConfig(BaseConfig):
    width: int
    height: int
    def validate(self):
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Width and Height must be positive.")

class ImageResizer(BaseProcessor):
    """
    通用缩放处理器
    """
    @property
    def name(self) -> str:
        return "resizer"

    @property
    def display_name(self) -> str:
        return "图片缩放 (Resizer)"

    def process(self, image: Image.Image, config: ResizeConfig) -> List[Tuple[Image.Image, Dict[str, Any]]]:
        new_img = image.resize((config.width, config.height), Image.Resampling.LANCZOS)
        # 对于缩放，通常只返回一张图
        context = {"action": "resized", "w": config.width, "h": config.height}
        return [(new_img, context)]
