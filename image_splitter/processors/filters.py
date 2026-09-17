"""Filter processor for applying visual effects like grayscale and inversion."""
from typing import Any, Dict, List, Tuple

from PIL import Image, ImageOps

from image_splitter.engine.base import BaseProcessor
from image_splitter.models import FilterConfig


class SimpleFilterProcessor(BaseProcessor):
    """Simple filter processor.

    Applies grayscale and invert filters.
    """
    @property
    def config_model(self) -> type:
        return FilterConfig
    @property
    def name(self) -> str:
        return "filters"
    @property
    def display_name(self) -> str:
        return "Effects"
    @property
    def category(self) -> str:
        return "Filter"
    @property
    def tool_tip(self) -> str:
        return "Apply grayscale or invert filter."
    def process(
        self,
        image: Image.Image,
        config: Dict[str, Any]
    ) -> List[Tuple[Image.Image, Dict[str, Any]]]:
        """Perform filter processing."""
        gs = config.get("grayscale", False)
        inv = config.get("invert", False)
        img = image.copy()
        if gs:
            # Preserve the alpha channel for RGBA/LA images.  The previous
            # `convert("L").convert("RGB")` path silently dropped alpha,
            # turning a transparent PNG into an opaque one.  Split, grayscale
            # only the colour channels, then recombine with the original
            # alpha so transparency survives.
            if img.mode == "RGBA":
                r, g, b, a = img.split()
                gray = Image.merge("RGB", (r, g, b)).convert("L")
                img = Image.merge("RGBA", (gray, gray, gray, a))
            elif img.mode == "LA":
                lum, alpha = img.split()
                img = Image.merge("LA", (lum, alpha))
            else:
                img = img.convert("L").convert("RGB")
        if inv:
            if img.mode == 'RGBA':
                r, g, b, a = img.split()
                rgb = Image.merge('RGB', (r, g, b))
                inv_rgb = ImageOps.invert(rgb)
                r, g, b = inv_rgb.split()
                img = Image.merge('RGBA', (r, g, b, a))
            elif img.mode == 'LA':
                # P1-4: Handle LA mode separately — ImageOps.invert on
                # LA fails. Split into L + A, invert L, recombine.
                l_channel, a_channel = img.split()
                inv_l = ImageOps.invert(l_channel)
                img = Image.merge('LA', (inv_l, a_channel))
            elif img.mode == 'P':
                img = img.convert("RGB")
                img = ImageOps.invert(img)
            else:
                img = ImageOps.invert(img)
        return [(img, {"action": "filter"})]
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
            def get_val(key: str) -> Any:
                v = props.get(key)
                if v is None:
                    return None
                return v.get() if hasattr(v, 'get') else v
            gs = get_val("grayscale")
            inv = get_val("invert")
            if not gs and not inv:
                return
            x0, y0 = canvas_pos
            canvas.create_text(
                x0 + 10, y0 + 10,
                text="[FX Active]",
                fill=theme.SUCCESS,
                anchor="nw",
                font=("Arial", 8),
                tags="overlay"
            )
        except Exception:
            pass
