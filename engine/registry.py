# image_splitter/engine/registry.py
from typing import Dict, Any, List

_global_registry: "ProcessorRegistry" = None


class ProcessorRegistry:
    """集中式处理器注册中心 (支持实例化和全局单例模式)"""

    _processors: Dict[str, Any] = {}

    def __init__(self):
        pass

    @classmethod
    def get_global_registry(cls) -> "ProcessorRegistry":
        """获取全局单例注册中心 (用于实例化调用场景)"""
        global _global_registry
        if _global_registry is None:
            _global_registry = cls()
        return _global_registry

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
