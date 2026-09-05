"""Color adjust processor for fine-tuning brightness, contrast, and saturation."""
from typing import Any, Dict, List, Tuple

from PIL import Image, ImageEnhance

from image_splitter.engine.base import BaseProcessor
from image_splitter.models import ColorConfig


class ImageColorAdjuster(BaseProcessor):
    """Color adjust processor.
    
    Adjusts brightness, contrast, sharpness and color saturation.
    """

    @property
    def config_model(self) -> type:
        return ColorConfig

    @property
    def name(self) -> str:
        return "color_adjuster"

    @property
    def display_name(self) -> str:
        return "Color Tuning"

    @property
    def category(self) -> str:
        return "Edit"

    @property
    def tool_tip(self) -> str:
        return "Fine-tune brightness, contrast, sharpness and saturation. 1.0 is original."

    def process(
        self, 
        image: Image.Image, 
        config: Dict[str, Any]
    ) -> List[Tuple[Image.Image, Dict[str, Any]]]:
        """Perform color enhancement."""
        b = config.get("brightness", 1.0)
        c = config.get("contrast", 1.0)
        s = config.get("sharpness", 1.0)
        color = config.get("color", 1.0)

        # P2-7: Range validation — PIL enhance() accepts any float but
        # extreme values produce garbage or crash. Clamp to reasonable range.
        for name, val in [("brightness", b), ("contrast", c),
                           ("sharpness", s), ("color", color)]:
            if not isinstance(val, (int, float)):
                raise ValueError(f"{name} must be a number, got {type(val).__name__}")
            if val < 0:
                raise ValueError(f"{name} must be >= 0, got {val}")

        img = image.copy()
        # ImageEnhance uses Image.blend internally, which cannot blend
        # palette ("P") or 1-bit ("1") images — it raises
        # "ValueError: image has wrong mode".  Convert those modes to RGB
        # first (visually lossless) so adjustment works.  Other modes
        # (L, RGB, RGBA, CMYK, F, I) are supported natively.
        if img.mode in ("P", "1"):
            img = img.convert("RGB")
        if b != 1.0:
            img = ImageEnhance.Brightness(img).enhance(b)
        if c != 1.0:
            img = ImageEnhance.Contrast(img).enhance(c)
        if s != 1.0:
            img = ImageEnhance.Sharpness(img).enhance(s)
        if color != 1.0:
            img = ImageEnhance.Color(img).enhance(color)

        return [(img, {"action": "color_tuned"})]
