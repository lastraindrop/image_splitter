# processors/watermark.py
from PIL import Image, ImageDraw, ImageFont
from typing import List, Dict, Any, Tuple
from image_splitter.engine.base import BaseProcessor

class TextWatermark(BaseProcessor):
    """
    文字水印处理器
    """
    @property
    def name(self) -> str:
        return "text_watermark"

    @property
    def display_name(self) -> str:
        return "文字水印 (Text Watermark)"

    @property
    def category(self) -> str:
        return "Security"

    def get_ui_metadata(self) -> List[Dict[str, Any]]:
        return [
            {"name": "text", "label": "水印文字", "type": "str", "default": "PROTOTYPE-V4"},
            {"name": "size", "label": "字体大小 (px)", "type": "int", "default": 40},
            {"name": "opacity", "label": "不透明度 (0-255)", "type": "int", "default": 128},
            {"name": "anchor", "label": "位置 (TL,TR,BL,BR,C)", "type": "str", "default": "BR"}
        ]

    def process(self, image: Image.Image, config: Any) -> List[Tuple[Image.Image, Dict[str, Any]]]:
        if isinstance(config, dict):
            text, size, opacity, anchor = config.get("text", ""), config.get("size", 40), config.get("opacity", 128), config.get("anchor", "BR")
        else:
            text, size, opacity, anchor = config.text, config.size, config.opacity, config.anchor

        img = image.convert("RGBA")
        txt_layer = Image.new("RGBA", img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(txt_layer)
        
        try:
            font = ImageFont.truetype("arial.ttf", size)
        except:
            font = ImageFont.load_default()
            
        w, h = img.size
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        
        padding = 20
        if anchor == "TL": x, y = padding, padding
        elif anchor == "TR": x, y = w - tw - padding, padding
        elif anchor == "BL": x, y = padding, h - th - padding
        elif anchor == "BR": x, y = w - tw - padding, h - th - padding
        else: x, y = (w - tw) // 2, (h - th) // 2 
        
        draw.text((x, y), text, font=font, fill=(255, 255, 255, opacity))
        out = Image.alpha_composite(img, txt_layer)
        if image.mode != "RGBA":
            out = out.convert(image.mode)

        return [(out, {"action": "watermarked", "text": text, "anchor": anchor})]

    def draw_preview(self, canvas, thumb_size, canvas_pos, ratio, props, theme):
        try:
            anchor = props.get("anchor").get() or "BR"
            text = props.get("text").get() or "PREVIEW"
            
            cw, ch = thumb_size
            x0, y0 = canvas_pos
            
            tw, th = 60, 20
            m = 10
            if anchor == "TL": px, py = x0+m, y0+m
            elif anchor == "TR": px, py = x0+cw-tw-m, y0+m
            elif anchor == "BL": px, py = x0+m, y0+ch-th-m
            elif anchor == "BR": px, py = x0+cw-tw-m, y0+ch-th-m
            else: px, py = x0+(cw-tw)//2, y0+(ch-th)//2
            
            canvas.create_rectangle(px, py, px+tw, py+th, fill=theme.PRIMARY, stipple="gray50", outline="white", tags="overlay")
            canvas.create_text(px+tw//2, py+th//2, text=text[:6], fill="white", font=("Arial", 7), tags="overlay")
        except: pass
