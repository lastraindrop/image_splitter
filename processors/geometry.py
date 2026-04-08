# image_splitter/processors/geometry.py
from PIL import Image
from typing import List, Dict, Any, Tuple
from image_splitter.engine.base import BaseProcessor

class GeometryProcessor(BaseProcessor):
    """
    几何变换处理器：旋转与翻转
    """
    @property
    def name(self) -> str:
        return "geometry"

    @property
    def display_name(self) -> str:
        return "几何变换 (Rotate & Flip)"

    @property
    def category(self) -> str:
        return "Transform"

    def get_ui_metadata(self) -> List[Dict[str, Any]]:
        return [
            {"name": "rotate", "label": "旋转角度 (0, 90, 180, 270)", "type": "int", "default": 0},
            {"name": "flip_h", "label": "水平翻转 (True/False)", "type": "bool", "default": False},
            {"name": "flip_v", "label": "垂直翻转 (True/False)", "type": "bool", "default": False}
        ]

    def process(self, image: Image.Image, config: Any) -> List[Tuple[Image.Image, Dict[str, Any]]]:
        angle = int(config.get("rotate", 0)) if isinstance(config, dict) else int(getattr(config, 'rotate', 0))
        fh = config.get("flip_h", False) if isinstance(config, dict) else getattr(config, 'flip_h', False)
        fv = config.get("flip_v", False) if isinstance(config, dict) else getattr(config, 'flip_v', False)

        img = image.copy()
        
        # 旋转 (使用内建转置以保证质量与效率)
        if angle == 90: img = img.transpose(Image.ROTATE_90)
        elif angle == 180: img = img.transpose(Image.ROTATE_180)
        elif angle == 270: img = img.transpose(Image.ROTATE_270)
        
        # 翻转
        if str(fh).lower() == "true": img = img.transpose(Image.FLIP_LEFT_RIGHT)
        if str(fv).lower() == "true": img = img.transpose(Image.FLIP_TOP_BOTTOM)

        return [(img, {"action": "geometry", "rotate": angle})]

    def draw_preview(self, canvas, thumb_size, canvas_pos, ratio, props, theme):
        # 绘制旋转预览提示
        try:
            angle = int(props.get("rotate").get() or 0)
            if angle == 0: return
            
            cw, ch = thumb_size
            x0, y0 = canvas_pos
            
            # 在中心画一个旋转图标
            cx, cy = x0 + cw//2, y0 + ch//2
            canvas.create_oval(cx-20, cy-20, cx+20, cy+20, outline=theme.PRIMARY, width=2, tags="overlay")
            canvas.create_text(cx, cy, text=f"{angle}°", fill=theme.PRIMARY, font=("Arial", 10, "bold"), tags="overlay")
        except Exception:
            pass
