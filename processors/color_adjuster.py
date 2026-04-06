# processors/color_adjuster.py
from PIL import Image, ImageEnhance
from typing import List, Dict, Any, Tuple
from image_splitter.engine.base import BaseProcessor

class ImageColorAdjuster(BaseProcessor):
    """
    色彩与图像质量调节器 (Brightness, Contrast, Sharpness, Color)
    """
    @property
    def name(self) -> str:
        return "color_adjuster"

    @property
    def display_name(self) -> str:
        return "色彩调节 (Color Tuning)"

    @property
    def category(self) -> str:
        return "Edit"

    def get_ui_metadata(self) -> List[Dict[str, Any]]:
        return [
            {"name": "brightness", "label": "亮度 (1.0=原图)", "type": "float", "default": 1.0},
            {"name": "contrast", "label": "对比度", "type": "float", "default": 1.0},
            {"name": "sharpness", "label": "锐度", "type": "float", "default": 1.0},
            {"name": "color", "label": "颜色/饱和度", "type": "float", "default": 1.0}
        ]

    def process(self, image: Image.Image, config: Any) -> List[Tuple[Image.Image, Dict[str, Any]]]:
        if isinstance(config, dict):
            b, c, s, color = config.get("brightness", 1.0), config.get("contrast", 1.0), config.get("sharpness", 1.0), config.get("color", 1.0)
        else:
            b, c, s, color = getattr(config, 'brightness', 1.0), getattr(config, 'contrast', 1.0), getattr(config, 'sharpness', 1.0), getattr(config, 'color', 1.0)

        img = image.copy()
        if b != 1.0: img = ImageEnhance.Brightness(img).enhance(b)
        if c != 1.0: img = ImageEnhance.Contrast(img).enhance(c)
        if s != 1.0: img = ImageEnhance.Sharpness(img).enhance(s)
        if color != 1.0: img = ImageEnhance.Color(img).enhance(color)

        return [(img, {"action": "color_tuned"})]
