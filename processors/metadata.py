# image_splitter/processors/metadata.py
from typing import Any, Dict, List, Tuple

from PIL import Image

from image_splitter.engine.base import BaseProcessor
from image_splitter.models import MetadataConfig


class MetadataProcessor(BaseProcessor):
    """元数据处理器。
    
    支持剥离隐私元数据（EXIF/GPS 等），并可选择保留 ICC 色彩配置文件。
    """

    @property
    def config_model(self) -> type:
        return MetadataConfig

    @property
    def name(self) -> str:
        return "metadata_cleaner"

    @property
    def display_name(self) -> str:
        return "元数据清理 (Metadata Cleaner)"

    @property
    def category(self) -> str:
        return "Export"

    @property
    def tool_tip(self) -> str:
        return "剥离图像中的隐私元数据（如 EXIF/GPS），显著减小体积 (Metadata Cleaner)。"

    def get_ui_metadata(self) -> List[Dict[str, Any]]:
        return [
            {"name": "strip_all", "label": "剥离所有元数据", "type": "bool", "default": True},
            {"name": "keep_icc", "label": "保留 ICC 配置文件", "type": "bool", "default": True}
        ]

    def process(
        self, 
        image: Image.Image, 
        config: Dict[str, Any]
    ) -> List[Tuple[Image.Image, Dict[str, Any]]]:
        """执行元数据清理。"""
        strip = config.get("strip_all", True)
        keep_icc = config.get("keep_icc", True)

        context = {"action": "metadata_cleaned"}
        if not strip:
            return [(image.copy(), context)]

        # 创建纯净副本
        clean_img = Image.new(image.mode, image.size)
        clean_img.paste(image)
        
        # 处理 ICC Profile
        icc = image.info.get("icc_profile")
        if keep_icc and icc:
            clean_img.info["icc_profile"] = icc
            context["icc"] = "preserved"

        return [(clean_img, context)]

    def draw_preview(self, canvas, thumb_size, canvas_pos, ratio, props, theme):
        try:
            def get_val(key):
                v = props.get(key)
                return v.get() if hasattr(v, 'get') else v

            active = get_val("strip_all")
            if not active:
                return
            
            x0, y0 = canvas_pos
            canvas.create_text(
                x0 + 10, y0 + 10, 
                text="🛡 隐私保护已开启", 
                fill=theme.SUCCESS, 
                anchor="nw", 
                font=("Arial", 8), 
                tags="overlay"
            )
        except Exception:
            pass
