"""Engine package - core processing infrastructure."""
from .base import BaseProcessor
from .dispatcher import CommandDispatcher
from .registry import ProcessorRegistry

__all__ = ["BaseProcessor", "CommandDispatcher", "ProcessorRegistry"]
