"""Metadata processor for cleaning privacy-sensitive EXIF/GPS information."""
# image_splitter/processors/metadata.py
from typing import Any, Dict, List, Tuple, Optional

from PIL import Image

from image_splitter.engine.base import BaseProcessor
from image_splitter.models import MetadataConfig


class MetadataProcessor(BaseProcessor):
    """Metadata processor.
    
    Strips privacy metadata (EXIF/GPS) with optional ICC profile retention.
    """

    @property
    def config_model(self) -> type:
        return MetadataConfig

    @property
    def name(self) -> str:
        return "metadata_cleaner"

    @property
    def display_name(self) -> str:
        return "Metadata Cleaner"

    @property
    def category(self) -> str:
        return "Export"

    @property
    def tool_tip(self) -> str:
        return "Strip privacy metadata (EXIF/GPS) to reduce file size."

    def get_ui_metadata(self) -> List[Dict[str, Any]]:
        return [
            {"name": "strip_all", "label": "Strip All Metadata", "type": "bool", "default": True},
            {"name": "keep_icc", "label": "Keep ICC Profile", "type": "bool", "default": True}
        ]

    def process(
        self,
        image: Image.Image,
        config: Dict[str, Any]
    ) -> List[Tuple[Image.Image, Dict[str, Any]]]:
        """Perform metadata cleanup."""
        strip = config.get("strip_all", True)
        keep_icc = config.get("keep_icc", True)

        context = {"action": "metadata_cleaned"}
        if not strip:
            return [(image.copy(), context)]

        # Save original palette (for P mode)
        original_palette: Optional[List[int]] = None
        if image.mode == "P":
            palette = image.getpalette()
            if palette:
                original_palette = list(palette)

        # Create clean copy
        clean_img = Image.new(image.mode, image.size)
        clean_img.paste(image)

        # Restore P mode palette
        if original_palette and image.mode == "P":
            clean_img.putpalette(original_palette)

        # Process ICC Profile
        icc = image.info.get("icc_profile")
        if keep_icc and icc:
            clean_img.info["icc_profile"] = icc
            context["icc"] = "preserved"

        return [(clean_img, context)]

    def draw_preview(
        self,
        canvas: Any,
        thumb_size: Tuple[int, int],
        canvas_pos: Tuple[int, int],
        ratio: float,
        props: Dict[str, Any],
        theme: Any
    ) -> None:
        try:
            def get_val(key):
                v = props.get(key)
                return v.get() if hasattr(v, 'get') else v

            active = get_val("strip_all")
            if not active:
                return
            
            x0, y0 = canvas_pos
            canvas.create_text(
                x0 + 10, y0 + 10, 
                text="Privacy ON", 
                fill=theme.SUCCESS, 
                anchor="nw", 
                font=("Arial", 8), 
                tags="overlay"
            )
        except Exception:
            pass
