# image_splitter/processors/adjuster.py
from PIL import Image
from typing import List, Dict, Any, Tuple
from engine.base import BaseProcessor
from models import AdjustConfig

class CanvasAdjuster(BaseProcessor):
    """
    画布调整处理器：增添/裁剪/填充
    """
    @property
    def name(self) -> str:
        return "canvas_adjuster"

    @property
    def display_name(self) -> str:
        return "画布调整 (Canvas Adjuster)"

    def process(self, image: Image.Image, config: AdjustConfig) -> List[Tuple[Image.Image, Dict[str, Any]]]:
        orig_w, orig_h = image.size
        
        # 1. 自动计算目标尺寸
        target_w = int(orig_w * config.width) if isinstance(config.width, float) else int(config.width)
        target_h = int(orig_h * config.height) if isinstance(config.height, float) else int(config.height)
        
        # 2. 创建底色画布
        # 如果原图或背景有 Alpha 通道，使用 RGBA
        mode = "RGBA" if "A" in image.mode or len(config.bg_color) > 3 else "RGB"
        new_img = Image.new(mode, (target_w, target_h), config.bg_color)
        
        # 3. 计算对齐位置 (Anchor)
        paste_x, paste_y = 0, 0
        if config.anchor == "center":
            paste_x = (target_w - orig_w) // 2
            paste_y = (target_h - orig_h) // 2
        elif config.anchor == "top-left":
            paste_x, paste_y = 0, 0
        elif config.anchor == "top-right":
            paste_x = target_w - orig_w
            paste_y = 0
        elif config.anchor == "bottom-left":
            paste_x = 0
            paste_y = target_h - orig_h
        elif config.anchor == "bottom-right":
            paste_x = target_w - orig_w
            paste_y = target_h - orig_h
            
        # 4. 合成图像 (Padding 或 Cropping 均通过此 paste 完成)
        # 注意：如果 paste_x 为负，Pillow 会自动执行裁剪效果
        if mode == "RGBA":
            # 透明度混合处理
            temp_img = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
            temp_img.paste(image, (paste_x, paste_y))
            new_img = Image.alpha_composite(new_img.convert("RGBA"), temp_img)
        else:
            new_img.paste(image, (paste_x, paste_y))
            
        context = {
            "action": "adjusted",
            "orig_w": orig_w,
            "orig_h": orig_h,
            "target_w": target_w,
            "target_h": target_h,
            "anchor": config.anchor
        }
        
        return [(new_img, context)]
