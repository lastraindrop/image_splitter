# image_splitter/processors/format_converter.py
from typing import Any, Dict, List, Tuple

from PIL import Image

from image_splitter.engine.base import BaseProcessor
from image_splitter.models import FormatConfig


class ImageFormatConverter(BaseProcessor):
    """图像格式转换器。
    
    支持 WebP, JPEG, PNG, BMP 格式转换及质量控制。
    """

    @property
    def config_model(self) -> type:
        return FormatConfig

    @property
    def name(self) -> str:
        return "format_converter"

    @property
    def display_name(self) -> str:
        return "格式转换 (Format Converter)"

    @property
    def category(self) -> str:
        return "Export"

    @property
    def tool_tip(self) -> str:
        return "将图像导出为指定的格式，支持调节压缩质量 (Format Converter)。"

    def get_ui_metadata(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "format", 
                "label": "目标格式", 
                "type": "enum", 
                "default": "WebP", 
                "options": ["WebP", "JPEG", "PNG", "BMP"]
            },
            {"name": "quality", "label": "质量 (1-100)", "type": "int", "default": 80}
        ]

    def process(
        self, 
        image: Image.Image, 
        config: Dict[str, Any]
    ) -> List[Tuple[Image.Image, Dict[str, Any]]]:
        """执行格式转换。"""
        fmt = config.get("format", "WebP")
        quality = config.get("quality", 80)
            
        ext_map = {"WebP": "webp", "JPEG": "jpg", "PNG": "png", "BMP": "bmp"}
        new_ext = ext_map.get(fmt, "webp")
        
        return [(image.copy(), {"action": "converted", "ext": new_ext, "quality": quality})]
