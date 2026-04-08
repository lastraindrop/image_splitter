# image_splitter/processors/metadata.py
from PIL import Image
from typing import List, Dict, Any, Tuple
from image_splitter.engine.base import BaseProcessor

class MetadataProcessor(BaseProcessor):
    """
    元数据处理器：剥离 EXIF/IPTC 等隐私信息，减小文件体积
    """
    @property
    def name(self) -> str:
        return "metadata_cleaner"

    @property
    def display_name(self) -> str:
        return "元数据清理 (Metadata Cleaner)"

    @property
    def category(self) -> str:
        return "Export"

    def get_ui_metadata(self) -> List[Dict[str, Any]]:
        return [
            {"name": "strip_all", "label": "剥离所有元数据 (EXIF等)", "type": "bool", "default": True},
            {"name": "keep_icc", "label": "保留 ICC 色彩配置文件", "type": "bool", "default": True}
        ]

    def process(self, image: Image.Image, config: Any) -> List[Tuple[Image.Image, Dict[str, Any]]]:
        strip = config.get("strip_all", True) if isinstance(config, dict) else getattr(config, 'strip_all', True)
        keep_icc = config.get("keep_icc", True) if isinstance(config, dict) else getattr(config, 'keep_icc', True)

        context = {"action": "metadata_cleaned"}
        
        if not strip:
            return [(image.copy(), context)]

        # 创建一个纯净的副本，不携带 orig_img.info
        clean_img = Image.new(image.mode, image.size)
        clean_img.paste(image)
        
        # 处理 ICC Profile (如果需要保留)
        icc = image.info.get("icc_profile")
        if keep_icc and icc:
            clean_img.info["icc_profile"] = icc
            context["icc"] = "preserved"

        return [(clean_img, context)]

    def draw_preview(self, canvas, thumb_size, canvas_pos, ratio, props, theme):
        # 元数据清理在视觉上无变化，绘制一个小绿点提示
        try:
            active = props.get("strip_all").get()
            if not active: return
            
            x0, y0 = canvas_pos
            canvas.create_text(x0 + 10, y0 + 10, text="🛡 隐私保护已开启", fill=theme.SUCCESS, anchor="nw", font=("Arial", 8), tags="overlay")
        except Exception:
            pass
