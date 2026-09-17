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
        2. Estimate the background level (alpha assumes transparent bg;
           luminance samples the border frame — works for both dark and
           light backgrounds).
        3. Threshold: pixels differing from the background by more than
           ``threshold`` are content.
        4. Compute the bounding box of content pixels.
        5. Expand by ``margin`` and crop.
    """

    @staticmethod
    def _estimate_bg_level(lum: "Image.Image") -> int:
        """Estimate background luminance from a thin border frame.

        V15: the luminance path previously assumed a *dark* background
        (``p > threshold`` = content), which made smart_crop a no-op on
        white-background images — the most common real-world case
        (scans, screenshots, product shots).  Border sampling makes the
        detection background-agnostic.
        """
        from PIL import ImageStat

        w, h = lum.size
        t = max(1, min(2, w // 10, h // 10))
        strips = [
            lum.crop((0, 0, w, t)),          # top
            lum.crop((0, h - t, w, h)),      # bottom
            lum.crop((0, 0, t, h)),          # left
            lum.crop((w - t, 0, w, h)),      # right
        ]
        total = 0.0
        count = 0
        for strip in strips:
            stat = ImageStat.Stat(strip)
            total += stat.mean[0] * strip.size[0] * strip.size[1]
            count += strip.size[0] * strip.size[1]
        return int(total / count) if count else 0

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
            # Use alpha channel directly (transparent background)
            mask = image.getchannel("A").point(
                lambda p: 255 if p > threshold else 0
            )
        else:
            # Use luminance difference from the estimated background
            # level — content is "sufficiently different from the bg".
            lum = image.convert("L")
            bg_level = SmartCropProcessor._estimate_bg_level(lum)
            mask = lum.point(
                lambda p: 255 if abs(p - bg_level) > threshold else 0
            )

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
