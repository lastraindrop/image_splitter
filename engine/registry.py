# image_splitter/engine/registry.py
from typing import Dict, Type
from .base import BaseProcessor

class ProcessorRegistry:
    """插件注册表"""
    _processors: Dict[str, BaseProcessor] = {}

    @classmethod
    def register(cls, processor: BaseProcessor):
        """注册一个处理器"""
        cls._processors[processor.name] = processor

    @classmethod
    def get(cls, name: str) -> BaseProcessor:
        """获取处理器"""
        if name not in cls._processors:
            raise ValueError(f"Processor '{name}' not found.")
        return cls._processors[name]

    @classmethod
    def list_all(cls):
        """列出所有已注册的处理器"""
        return list(cls._processors.values())
