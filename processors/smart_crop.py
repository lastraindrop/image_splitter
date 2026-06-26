"""Content-aware (smart) crop processor.

Automatically crops an image to its visible content by analysing pixel
intensity edges, then optionally adds a safety margin.
"""

from typing import Any, Dict, List, Tuple

from PIL import Image

from image_splitter.engine.base import BaseProcessor
from image_splitter.models import SmartCropConfig


class SmartCropProcessor(BaseProcessor):
    """Content-aware smart crop processor.

    Analyses the image's alpha channel (for RGBA) or luminance edges
    to find the bounding box of visible content, then crops to that
    region with an optional margin.

    Algorithm:
        1. Convert to RGBA or L to get a single intensity channel.
        2. Threshold to find non-background pixels.
        3. Compute the bounding box of remaining pixels.
        4. Expand by ``margin`` and crop.
    """

    @property
    def config_model(self) -> type:
        return SmartCropConfig

    @property
    def name(self) -> str:
        return "smart_crop"

    @property
    def display_name(self) -> str:
        return "Smart Crop"

    @property
    def category(self) -> str:
        return "Transform"

    @property
    def tool_tip(self) -> str:
        return "Auto-crop to visible content using edge detection."

    def process(
        self,
        image: Image.Image,
        config: Dict[str, Any],
    ) -> List[Tuple[Image.Image, Dict[str, Any]]]:
        threshold = int(config.get("threshold", 30))
        margin = int(config.get("margin", 10))
        w, h = image.size

        if image.mode == "RGBA":
            # Use alpha channel directly
            alpha = image.getchannel("A")
        else:
            # Use luminance as proxy for "content"
            alpha = image.convert("L")

        # Apply threshold to find non-background pixels
        mask = alpha.point(lambda p: 255 if p > threshold else 0)

        # Get bounding box of non-zero pixels
        bbox = mask.getbbox()
        if bbox is None:
            # Image is entirely background — return as-is
            return [(image.copy(), {"action": "smart_crop", "cropped": False})]

        # Apply margin (clamped to image bounds)
        left = max(0, bbox[0] - margin)
        upper = max(0, bbox[1] - margin)
        right = min(w, bbox[2] + margin)
        lower = min(h, bbox[3] + margin)

        cropped = image.crop((left, upper, right, lower))
        return [(cropped, {"action": "smart_crop", "cropped": True,
                           "bbox": f"{left},{upper},{right},{lower}"})]
