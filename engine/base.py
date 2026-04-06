# image_splitter/engine/base.py
from abc import ABC, abstractmethod
from PIL import Image
from typing import List, Dict, Any, Tuple, Optional

class BaseConfig(ABC):
    """基础配置类"""
    @abstractmethod
    def validate(self):
        """校验配置合法性"""
        pass

class BaseProcessor(ABC):
    """图像处理器基类"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """处理器唯一名称"""
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """GUI 显示名称"""
        pass

    @property
    def category(self) -> str:
        """所属分类: Split, Transform, Edit, Filter, Export"""
        return "Transform"

    @property
    def tool_tip(self) -> str:
        """操作提示"""
        return ""

    @abstractmethod
    def process(self, image: Image.Image, config: Any) -> List[Tuple[Image.Image, Dict[str, Any]]]:
        """核心处理逻辑"""
        pass

    def get_ui_metadata(self) -> List[Dict[str, Any]]:
        """返回 UI 参数定义"""
        return []

    def draw_preview(self, canvas: Any, thumb_size: Tuple[int, int], canvas_pos: Tuple[int, int], ratio: float, props: Dict[str, Any], theme: Any):
        """绘制预览辅助线"""
        pass
