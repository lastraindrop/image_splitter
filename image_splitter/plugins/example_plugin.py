"""Example plugin: adds an invert colors operator.

This file demonstrates how to create a third-party processor plugin.
Place any .py file containing a BaseProcessor subclass in the plugins/
directory and it will be auto-discovered on startup.
"""
from typing import Any, Dict, List, Tuple

from PIL import Image, ImageOps

from image_splitter.engine.base import BaseProcessor


class InvertColorProcessor(BaseProcessor):
    """Invert image colors (negative effect).

    A simple example plugin demonstrating the plugin architecture.
    """

    @property
    def name(self) -> str:
        return "invert_color"

    @property
    def display_name(self) -> str:
        return "Invert Colors (Plugin)"

    @property
    def category(self) -> str:
        return "Filter"

    @property
    def tool_tip(self) -> str:
        return "Invert all colors - example user plugin."

    def get_ui_metadata(self) -> List[Dict[str, Any]]:
        return [
            {"name": "invert_alpha", "label": "Invert Alpha", "type": "bool", "default": False}
        ]

    def process(
        self,
        image: Image.Image,
        config: Dict[str, Any]
    ) -> List[Tuple[Image.Image, Dict[str, Any]]]:
        invert_alpha = config.get("invert_alpha", False)

        # P0-3: Handle RGBA and LA modes separately.
        # LA mode has only 2 channels (L + A), so bands[:3] would
        # produce only [L] — Image.merge("RGB", (L,)) raises ValueError.
        if image.mode == "RGBA":
            bands = list(image.split())
            rgb_bands = bands[:3]
            alpha_band = bands[3]

            merged_rgb = Image.merge("RGB", tuple(rgb_bands))
            inverted_rgb = ImageOps.invert(merged_rgb)
            inv_r, inv_g, inv_b = inverted_rgb.split()

            if invert_alpha:
                alpha_band = ImageOps.invert(alpha_band)
            result = Image.merge("RGBA", (inv_r, inv_g, inv_b, alpha_band))
        elif image.mode == "LA":
            bands = list(image.split())
            l_channel = bands[0]
            alpha_band = bands[1]

            # L channel: invert as grayscale, recombine with alpha
            inv_l = ImageOps.invert(l_channel)
            if invert_alpha:
                alpha_band = ImageOps.invert(alpha_band)
            result = Image.merge("LA", (inv_l, alpha_band))
        else:
            result = ImageOps.invert(image.convert("RGB"))

        return [(result, {"action": "inverted"})]

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
            x0, y0 = canvas_pos
            canvas.create_text(
                x0 + 5,
                y0 + 5,
                text="[Invert]",
                fill=theme.DANGER,
                anchor="nw",
                font=("Arial", 8, "bold"),
                tags="overlay",
            )
        except Exception:
            pass
