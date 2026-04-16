# image_splitter/processors/color_adjuster.py
from typing import Any, Dict, List, Tuple

from PIL import Image, ImageEnhance

from image_splitter.engine.base import BaseProcessor
from image_splitter.models import ColorConfig


class ImageColorAdjuster(BaseProcessor):
    """色彩与图像质量调节器。
    
    支持调节亮度、对比度、锐度及颜色饱和度。
    """

    @property
    def config_model(self) -> type:
        return ColorConfig

    @property
    def name(self) -> str:
        return "color_adjuster"

    @property
    def display_name(self) -> str:
        return "色彩调节 (Color Tuning)"

    @property
    def category(self) -> str:
        return "Edit"

    @property
    def tool_tip(self) -> str:
        return "精细调节图像的亮度、对比度、锐度及饱和度。1.0 即为原图 (Color Tuning)。"

    def get_ui_metadata(self) -> List[Dict[str, Any]]:
        return [
            {"name": "brightness", "label": "亮度", "type": "float", "default": 1.0},
            {"name": "contrast", "label": "对比度", "type": "float", "default": 1.0},
            {"name": "sharpness", "label": "锐度", "type": "float", "default": 1.0},
            {"name": "color", "label": "颜色/饱和度", "type": "float", "default": 1.0}
        ]

    def process(
        self, 
        image: Image.Image, 
        config: Dict[str, Any]
    ) -> List[Tuple[Image.Image, Dict[str, Any]]]:
        """执行色彩增强处理。"""
        b = config.get("brightness", 1.0)
        c = config.get("contrast", 1.0)
        s = config.get("sharpness", 1.0)
        color = config.get("color", 1.0)

        img = image.copy()
        if b != 1.0:
            img = ImageEnhance.Brightness(img).enhance(b)
        if c != 1.0:
            img = ImageEnhance.Contrast(img).enhance(c)
        if s != 1.0:
            img = ImageEnhance.Sharpness(img).enhance(s)
        if color != 1.0:
            img = ImageEnhance.Color(img).enhance(color)

        return [(img, {"action": "color_tuned"})]
