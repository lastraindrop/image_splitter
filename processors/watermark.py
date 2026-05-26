"""Text watermark processor for adding semi-transparent labels to images."""
import platform
from typing import Any, Dict, List, Tuple

from PIL import Image, ImageDraw, ImageFont

from image_splitter.engine.base import BaseProcessor
from image_splitter.models import WatermarkConfig

_FONT_SEARCH_PATHS = {
    "Windows": ["arial.ttf", "C:/Windows/Fonts/arial.ttf"],
    "Darwin": [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNSMono.ttf",
        "/Library/Fonts/Arial.ttf",
    ],
    "Linux": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ],
}


def _load_font(size: int):
    """Load a usable font for the current platform.
    
    Returns:
        A font object suitable for use with PIL ImageDraw.
    """
    system = platform.system()
    candidates = _FONT_SEARCH_PATHS.get(system, []) + ["arial.ttf"]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default(size=size)


class TextWatermark(BaseProcessor):
    """Text watermark processor.
    
    Adds semi-transparent text watermark at specified positions.
    """

    @property
    def config_model(self) -> type:
        return WatermarkConfig

    @property
    def name(self) -> str:
        return "text_watermark"

    @property
    def display_name(self) -> str:
        return "Text Watermark"

    @property
    def category(self) -> str:
        return "Edit"

    @property
    def tool_tip(self) -> str:
        return "Add semi-transparent text watermark at specified position."

    def get_ui_metadata(self) -> List[Dict[str, Any]]:
        return [
            {"name": "text", "label": "Text", "type": "str", "default": "PROTOTYPE"},
            {"name": "size", "label": "Font Size", "type": "int", "default": 40},
            {"name": "opacity", "label": "Opacity", "type": "int", "default": 128},
            {
                "name": "anchor", 
                "label": "Position", 
                "type": "enum", 
                "default": "BR", 
                "options": ["TL", "TR", "BL", "BR", "C"]
            }
        ]

    def process(
        self, 
        image: Image.Image, 
        config: Dict[str, Any]
    ) -> List[Tuple[Image.Image, Dict[str, Any]]]:
        """Add text watermark."""
        text = config.get("text", "")
        opacity = int(float(config.get("opacity", 128)))
        size = int(float(config.get("size", 40)))
        anchor = config.get("anchor", "BR")

        img = image.convert("RGBA")
        txt_layer = Image.new("RGBA", img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(txt_layer)

        font = _load_font(size)

        w, h = img.size
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = int(bbox[2] - bbox[0])
        th = int(bbox[3] - bbox[1])

        padding = 20
        if anchor == "TL": 
            x, y = padding, padding
        elif anchor == "TR": 
            x, y = w - tw - padding, padding
        elif anchor == "BL": 
            x, y = padding, h - th - padding
        elif anchor == "BR": 
            x, y = w - tw - padding, h - th - padding
        else: 
            x, y = (w - tw) // 2, (h - th) // 2 

        draw.text((x, y), text, font=font, fill=(255, 255, 255, opacity))

        composited = Image.alpha_composite(img, txt_layer)

        context = {
            "action": "watermarked",
            "text": text,
            "anchor": anchor,
        }

        return [(composited, context)]

    def draw_preview(self, canvas: Any, thumb_size: Tuple[int, int], canvas_pos: Tuple[int, int], ratio: float, props: Dict[str, Any], theme: Any) -> None:
        try:
            def get_val(key: str) -> Any:
                v = props.get(key)
                if v is None:
                    return None
                return v.get() if hasattr(v, 'get') else v


            anchor = get_val("anchor") or "BR"
            text = get_val("text") or "PREVIEW"
            
            cw, ch = thumb_size
            x0, y0 = canvas_pos
            
            tw, th = 60, 20
            m = 10
            if anchor == "TL": px, py = x0 + m, y0 + m
            elif anchor == "TR": px, py = x0 + cw - tw - m, y0 + m
            elif anchor == "BL": px, py = x0 + m, y0 + ch - th - m
            elif anchor == "BR": px, py = x0 + cw - tw - m, y0 + ch - th - m
            else: px, py = x0 + (cw - tw) // 2, y0 + (ch - th) // 2
            
            canvas.create_rectangle(
                px, py, px + tw, py + th, 
                fill=theme.PRIMARY, stipple="gray50", outline="white", tags="overlay"
            )
            canvas.create_text(
                px + tw // 2, py + th // 2, 
                text=text[:6], fill="white", font=("Arial", 7), tags="overlay"
            )
        except Exception:
            pass
