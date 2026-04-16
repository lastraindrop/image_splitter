# image_splitter/engine/base.py
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image


class BaseConfig(ABC):
    """基础配置抽象基类。"""
    @abstractmethod
    def validate(self) -> None:
        """校验配置合法性。

        Raises:
            ValueError: 当配置参数不合法时抛出。
        """
        pass


class BaseProcessor(ABC):
    """图像处理器插件基类。
    
    所有具体的处理器（如网格切割、缩放器）都必须继承此类并实现抽象方法。
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """处理器唯一标识名称（snake_case）。"""
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """GUI 界面显示的名称。"""
        pass

    @property
    def category(self) -> str:
        """所属分类。
        
        可选值: 'Split', 'Transform', 'Edit', 'Filter', 'Export'。
        """
        return "Transform"

    @property
    def tool_tip(self) -> str:
        """操作功能的简短提示说明。"""
        return ""

    @property
    def config_model(self) -> Optional[type]:
        """该处理器对应的配置验证模型类（DataClass）。"""
        return None

    @abstractmethod
    def process(
        self, 
        image: Image.Image, 
        config: Dict[str, Any]
    ) -> List[Tuple[Image.Image, Dict[str, Any]]]:
        """核心处理逻辑。

        Args:
            image: 输入的 PIL 图像对象。
            config: 清洗并转换类型后的配置字典。

        Returns:
            处理结果列表。每个元素是一个元组 (Image, Context)，
            Context 用于命名模板的占位符替换。
        """
        pass

    def get_ui_metadata(self) -> List[Dict[str, Any]]:
        """定义 UI 自动生成所需的参数元数据。

        Returns:
            参数定义列表。每个字典需包含 'name', 'label', 'type', 'default' 等字段。
        """
        return []

    def draw_preview(
        self, 
        canvas: Any, 
        thumb_size: Tuple[int, int], 
        canvas_pos: Tuple[int, int], 
        ratio: float, 
        props: Dict[str, Any], 
        theme: Any
    ) -> None:
        """在 GUI 画布上绘制预览辅助线或覆盖物。

        Args:
            canvas: tkinter.Canvas 对象。
            thumb_size: 缩略图在画布上的实际尺寸 (w, h)。
            canvas_pos: 缩略图左上角在画布上的坐标 (x, y)。
            ratio: 原始图到缩略图的缩放比例。
            props: 当前 UI 控件的变量字典。
            theme: UI 主题配置对象。
        """
        pass
