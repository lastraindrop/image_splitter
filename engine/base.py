# image_splitter/engine/base.py
from abc import ABC, abstractmethod
from PIL import Image
from typing import List, Dict, Any, Tuple

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

    @abstractmethod
    def process(self, image: Image.Image, config: Any) -> List[Tuple[Image.Image, Dict[str, Any]]]:
        """核心处理逻辑"""
        pass

    def get_ui_metadata(self) -> List[Dict[str, Any]]:
        """
        返回 UI 参数定义
        示例: [{"name": "rows", "label": "行数", "type": "int", "default": 3}]
        """
        return []
