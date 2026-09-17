"""Centralized registry for image processors."""
import logging
import threading
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ProcessorRegistry:
    """Centralized processor registry (supports instantiation and global singleton mode)"""

    _instance: Optional["ProcessorRegistry"] = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        self._processors: Dict[str, Any] = {}

    @classmethod
    def get_instance(cls) -> "ProcessorRegistry":
        """Get the global singleton instance (thread-safe)."""
        if cls._instance is None:
            with cls._lock:
                # Double-check after acquiring lock
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def register(cls, processor: Any, *, allow_override: bool = False) -> None:
        """Register a processor.

        Args:
            processor: The processor instance to register.
            allow_override: Permit replacing an already-registered name.
                Defaults to ``False`` — accidental duplicate registration
                raises instead of silently shadowing a processor (V15).
                User plugins are scanned with ``allow_override=True`` so
                they can deliberately override built-in processors.

        Raises:
            ValueError: If *processor.name* is already registered and
                *allow_override* is ``False``.
        """
        inst = cls.get_instance()
        if processor.name in inst._processors:
            old = inst._processors[processor.name]
            if not allow_override:
                raise ValueError(
                    f"Processor '{processor.name}' is already registered "
                    f"({type(old).__name__}); pass allow_override=True to "
                    f"replace it explicitly"
                )
            logger.warning(
                "Processor '%s' re-registered: %s replaced by %s",
                processor.name,
                type(old).__name__,
                type(processor).__name__,
            )
        inst._processors[processor.name] = processor

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
