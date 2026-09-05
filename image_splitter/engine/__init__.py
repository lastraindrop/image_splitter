"""Engine package - core processing infrastructure."""
from .base import BaseProcessor
from .data_blocks import ImageDataBlock
from .dispatcher import CommandDispatcher
from .evaluator import EvaluationCache, NodeGraph
from .legacy_adapter import ChainAsGraph, ProcessorNodeAdapter
from .nodes import (
    BaseNode,
    BlendNode,
    ColorAdjustNode,
    Connection,
    ImageInputNode,
    ImageOutputNode,
    Socket,
    SocketType,
)
from .props import (
    BoolProp,
    ColorProp,
    EnumProp,
    FloatProp,
    IntProp,
    ListProp,
    Property,
    StrProp,
)
from .registry import ProcessorRegistry

__all__ = [
    # Legacy (unchanged)
    "BaseProcessor",
    "CommandDispatcher",
    "ProcessorRegistry",
    # Data blocks
    "ImageDataBlock",
    # Node graph
    "BaseNode",
    "BlendNode",
    "ColorAdjustNode",
    "Connection",
    "ImageInputNode",
    "ImageOutputNode",
    "NodeGraph",
    "EvaluationCache",
    "Socket",
    "SocketType",
    # Property system
    "Property",
    "BoolProp",
    "ColorProp",
    "EnumProp",
    "FloatProp",
    "IntProp",
    "ListProp",
    "StrProp",
    # Legacy adapter
    "ChainAsGraph",
    "ProcessorNodeAdapter",
]
