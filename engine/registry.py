# image_splitter/engine/registry.py
"""Centralized registry for image processors."""
from typing import Dict, Any, List, Optional


class ProcessorRegistry:
    """Centralized processor registry (supports instantiation and global singleton mode)"""

    _instance: Optional["ProcessorRegistry"] = None

    def __init__(self) -> None:
        self._processors: Dict[str, Any] = {}

    @classmethod
    def get_instance(cls) -> "ProcessorRegistry":
        """Get the global singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def register(cls, processor: Any) -> None:
        """Register a processor."""
        cls.get_instance()._processors[processor.name] = processor

    @classmethod
    def get(cls, name: str) -> Any:
        """Get a processor."""
        registry = cls.get_instance()
        if name not in registry._processors:
            raise ValueError(f"Processor not found: {name}")
        return registry._processors[name]

    @classmethod
    def list_all(cls) -> List[Any]:
        """List all registered processors."""
        return list(cls.get_instance()._processors.values())

    @classmethod
    def reset(cls) -> None:
        """Clear the registry."""
        cls.get_instance()._processors.clear()
