# processors/format_converter.py
from PIL import Image
from typing import List, Dict, Any, Tuple
from image_splitter.engine.base import BaseProcessor

class ImageFormatConverter(BaseProcessor):
    """
    格式转换器 (WebP, JPEG, PNG, etc.)
    """
    @property
    def name(self) -> str:
        return "format_converter"

    @property
    def display_name(self) -> str:
        return "格式转换 (Format Converter)"

    @property
    def category(self) -> str:
        return "Export"

    def get_ui_metadata(self) -> List[Dict[str, Any]]:
        return [
            {"name": "format", "label": "目标格式", "type": "enum", "default": "WebP", "options": ["WebP", "JPEG", "PNG", "BMP"]},
            {"name": "quality", "label": "质量 (1-100)", "type": "int", "default": 80}
        ]

    def process(self, image: Image.Image, config: Any) -> List[Tuple[Image.Image, Dict[str, Any]]]:
        if isinstance(config, dict):
            fmt = config.get("format", "WebP")
            quality = config.get("quality", 80)
        else:
            fmt, quality = getattr(config, 'format', 'WebP'), getattr(config, 'quality', 80)
            
        ext_map = {"WebP": ".webp", "JPEG": ".jpg", "PNG": ".png", "BMP": ".bmp"}
        new_ext = ext_map.get(fmt, ".webp")
        
        return [(image.copy(), {"action": "converted", "ext": new_ext.lstrip('.'), "quality": quality})]
