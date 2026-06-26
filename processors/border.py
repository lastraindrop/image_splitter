"""Border/frame processor — adds a configurable border around an image."""

from typing import Any, Dict, List, Tuple

from PIL import Image, ImageDraw, ImageOps

from image_splitter.engine.base import BaseProcessor
from image_splitter.models import BorderConfig


def _draw_dashed_hline(
    draw, x0: int, y: int, x1: int,
    color: str, dash_len: int, gap_len: int,
) -> None:
    """Draw a dashed horizontal line from x0 to x1 at y."""
    x = x0
    while x < x1:
        end = min(x + dash_len, x1)
        draw.line((x, y, end, y), fill=color)
        x = end + gap_len


def _draw_dashed_vline(
    draw, x: int, y0: int, y1: int,
    color: str, dash_len: int, gap_len: int,
) -> None:
    """Draw a dashed vertical line from y0 to y1 at x."""
    y = y0
    while y < y1:
        end = min(y + dash_len, y1)
        draw.line((x, y, x, end), fill=color)
        y = end + gap_len


class BorderProcessor(BaseProcessor):
    """Border/frame processor.

    Adds a solid, dashed, or double border around the image with
    configurable width and color.  The output image is enlarged
    to accommodate the border.
    """

    @property
    def config_model(self) -> type:
        return BorderConfig

    @property
    def name(self) -> str:
        return "border"

    @property
    def display_name(self) -> str:
        return "Border / Frame"

    @property
    def category(self) -> str:
        return "Transform"

    @property
    def tool_tip(self) -> str:
        return "Add a border or decorative frame to the image."

    def process(
        self,
        image: Image.Image,
        config: Dict[str, Any],
    ) -> List[Tuple[Image.Image, Dict[str, Any]]]:
        width = int(config.get("width", 4))
        color = config.get("color", "#3b82f6")
        style = config.get("style", "solid")

        # Expand the image with border
        if style == "double":
            # P1-2: Fix double border width.  Previous code produced
            # outer + inner + 1 = width + 1, whereas user asked for
            # exactly 'width'.  Account for the thin center line.
            inner_width = max(1, (width - 1) // 2)
            outer_width = width - inner_width - 1
            # Outer border
            result = ImageOps.expand(image, border=outer_width, fill=color)
            # Inner white gap
            result = ImageOps.expand(result, border=inner_width, fill="white")
            # Innermost thin colored line (1px)
            result = ImageOps.expand(result, border=1, fill=color)
        elif style == "dashed":
            # P2-10: Draw actual dash pattern via short line segments.
            result = ImageOps.expand(image, border=width, fill=color)
            w_final, h_final = result.size
            draw = ImageDraw.Draw(result)
            dash_len = max(4, width * 2)
            gap_len = max(3, width)
            # Draw dashed lines along each edge of the border region
            for offset in range(width):
                # Top edge: horizontal dashes at y=offset
                _draw_dashed_hline(draw, offset, offset, w_final - offset - 1,
                                   color, dash_len, gap_len)
                # Bottom edge: horizontal dashes at y=h-1-offset
                _draw_dashed_hline(draw, offset, h_final - offset - 1,
                                   w_final - offset - 1, color, dash_len, gap_len)
                # Left edge: vertical dashes at x=offset
                _draw_dashed_vline(draw, offset, offset, h_final - offset - 1,
                                   color, dash_len, gap_len)
                # Right edge: vertical dashes at x=w-1-offset
                _draw_dashed_vline(draw, w_final - offset - 1, offset,
                                   h_final - offset - 1, color, dash_len, gap_len)
        else:
            # Solid border
            result = ImageOps.expand(image, border=width, fill=color)

        return [(result, {"action": "border", "width": width, "color": color, "style": style})]
