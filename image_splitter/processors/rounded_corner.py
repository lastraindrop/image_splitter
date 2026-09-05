"""Rounded corner crop processor — crops image corners with configurable radius."""

from typing import Any, Dict, List, Tuple

from PIL import Image, ImageDraw

from image_splitter.engine.base import BaseProcessor
from image_splitter.models import RoundedCornerConfig


class RoundedCornerProcessor(BaseProcessor):
    """Rounded corner crop processor.

    Applies a rounded-corner mask to the image with configurable corner radius.
    The four corners are rounded by drawing a filled rounded rectangle mask
    on an alpha layer, then compositing it over a solid background.
    """

    @property
    def config_model(self) -> type:
        return RoundedCornerConfig

    @property
    def name(self) -> str:
        return "rounded_corner"

    @property
    def display_name(self) -> str:
        return "Rounded Corners"

    @property
    def category(self) -> str:
        return "Transform"

    @property
    def tool_tip(self) -> str:
        return "Crop image corners to rounded rectangle with configurable radius."

    def process(
        self,
        image: Image.Image,
        config: Dict[str, Any],
    ) -> List[Tuple[Image.Image, Dict[str, Any]]]:
        radius = int(config.get("radius", 20))
        w, h = image.size

        # Ensure radius doesn't exceed half the smallest dimension
        radius = min(radius, w // 2, h // 2)

        # Create a mask with rounded corners
        mask = Image.new("L", (w, h), 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle([(0, 0), (w - 1, h - 1)], radius=radius, fill=255)

        # Convert to RGBA and apply mask
        result = image.convert("RGBA")
        result.putalpha(mask)

        return [(result, {"action": "rounded_corners", "radius": radius})]
