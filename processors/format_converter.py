"""Format converter processor for changing image file types and quality."""
# image_splitter/processors/format_converter.py
from typing import Any, Dict, List, Tuple

from PIL import Image

from image_splitter.engine.base import BaseProcessor
from image_splitter.models import FormatConfig


class ImageFormatConverter(BaseProcessor):
    """Format converter processor.
    
    Converts image format (WebP, JPEG, PNG, BMP) with quality control.
    """

    @property
    def config_model(self) -> type:
        return FormatConfig

    @property
    def name(self) -> str:
        return "format_converter"

    @property
    def display_name(self) -> str:
        return "Format Converter"

    @property
    def category(self) -> str:
        return "Export"

    @property
    def tool_tip(self) -> str:
        return "Export image to specified format with quality control."

    def get_ui_metadata(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "format", 
                "label": "Target Format", 
                "type": "enum", 
                "default": "WebP", 
                "options": ["WebP", "JPEG", "PNG", "BMP"]
            },
            {"name": "quality", "label": "Quality (1-100)", "type": "int", "default": 80}
        ]

    def process(
        self, 
        image: Image.Image, 
        config: Dict[str, Any]
    ) -> List[Tuple[Image.Image, Dict[str, Any]]]:
        """Perform format conversion."""
        fmt = config.get("format", "WebP")
        quality = config.get("quality", 80)
            
        ext_map = {"WebP": "webp", "JPEG": "jpg", "PNG": "png", "BMP": "bmp"}
        new_ext = ext_map.get(fmt, "webp")
        
        return [(image.copy(), {"action": "converted", "ext": new_ext, "quality": quality})]
