# image_splitter/engine/registry.py
from typing import Dict, Any, List

class ProcessorRegistry:
    """集中式处理器注册中心"""
    _processors: Dict[str, Any] = {}

    @classmethod
    def register(cls, processor):
        """注册一个处理器"""
        cls._processors[processor.name] = processor

    @classmethod
    def get(cls, name: str):
        """获取处理器"""
        if name not in cls._processors:
            raise ValueError(f"未找到处理器: {name}")
        return cls._processors[name]

    @classmethod
    def list_all(cls):
        """列出所有已注册的处理器"""
        return list(cls._processors.values())

    @classmethod
    def reset(cls):
        """清空注册表"""
        cls._processors.clear()
