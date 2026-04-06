# image_splitter/engine/operator.py
from abc import ABC, abstractmethod
from typing import Any, Dict, List
from PIL import Image

class Operator(ABC):
    """
    对齐 Blender 设计的操作符基类
    """
    @property
    @abstractmethod
    def bl_idname(self) -> str:
        """操作符唯一标识符 (例如 'image.grid_split')"""
        pass

    @abstractmethod
    def execute(self, image: Image.Image, props: Dict[str, Any]) -> List[Any]:
        """执行逻辑"""
        pass

    def invoke(self, props: Dict[str, Any]):
        """在 UI 中调用时，可以进行参数交互或预校验"""
        pass
