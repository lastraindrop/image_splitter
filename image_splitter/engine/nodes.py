"""Node Graph primitives — SocketType, Socket, Connection, BaseNode, and concrete nodes.

Implements a DAG-based image processing pipeline inspired by Blender's compositor.
Each node declares typed input/output sockets and implements ``evaluate()`` to
produce output values from its inputs.
"""

from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from enum import auto
from typing import Any, Optional

from PIL import Image, ImageEnhance

# ---------------------------------------------------------------------------
# SocketType
# ---------------------------------------------------------------------------

class SocketType(enum.Enum):
    """Supported data types flowing through sockets."""

    IMAGE = auto()
    MASK = auto()
    VALUE = auto()
    COLOR = auto()


# ---------------------------------------------------------------------------
# Connection (forward-declared for Socket type hints)
# ---------------------------------------------------------------------------

class Connection:
    """A directed link from one output socket to one input socket.

    Validates at construction time that the direction and types are
    compatible, raising on mismatch.
    """

    def __init__(self, from_socket: Socket, to_socket: Socket) -> None:
        if from_socket.is_output == to_socket.is_output:
            raise ValueError(
                "Connection must link an output to an input; "
                f"got {'two outputs' if from_socket.is_output else 'two inputs'}"
            )
        if from_socket.is_output and not to_socket.is_output:
            # Normal direction: from output → to input
            pass
        else:
            raise ValueError(
                "Connection direction wrong: from_socket must be output, to_socket must be input"
            )
        if from_socket.socket_type != to_socket.socket_type:
            raise TypeError(
                f"Socket type mismatch: {from_socket.socket_type.name} → "
                f"{to_socket.socket_type.name}"
            )
        self.from_socket: Socket = from_socket
        self.to_socket: Socket = to_socket

    def __repr__(self) -> str:
        return (
            f"Connection({self.from_socket.node.display_name}.{self.from_socket.name} → "
            f"{self.to_socket.node.display_name}.{self.to_socket.name})"
        )


# ---------------------------------------------------------------------------
# Socket
# ---------------------------------------------------------------------------

class Socket:
    """A typed connection point on a node (either input or output).

    Attributes:
        name: Human-readable socket name.
        socket_type: The data type this socket carries.
        is_output: ``True`` for output sockets, ``False`` for inputs.
        connections: List of :class:`Connection` objects attached to this
            socket.
    """

    def __init__(
        self,
        name: str,
        socket_type: SocketType,
        is_output: bool,
        node: BaseNode,
    ) -> None:
        self.name: str = name
        self.socket_type: SocketType = socket_type
        self.is_output: bool = is_output
        self.node: BaseNode = node
        self.connections: list[Connection] = []
        self._value: Any = None

    # -- value property -----------------------------------------------------

    @property
    def value(self) -> Any:
        """Return the cached value for this socket."""
        return self._value

    @value.setter
    def value(self, new_value: Any) -> None:
        self._value = new_value

    def __repr__(self) -> str:
        direction = "out" if self.is_output else "in"
        return f"Socket({self.name!r}, {self.socket_type.name}, {direction})"


# ---------------------------------------------------------------------------
# Rebind Connection refs now that Socket is fully defined (for mypy)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# BaseNode (abstract)
# ---------------------------------------------------------------------------

class BaseNode(ABC):
    """Abstract base for all processing nodes in the graph.

    Subclasses must override :meth:`_setup_sockets` to declare their
    sockets and :meth:`evaluate` to perform their computation.
    """

    node_type: str = ""
    display_name: str = ""

    def __init__(self, name: str) -> None:
        self.name: str = name
        self.inputs: dict[str, Socket] = {}
        self.outputs: dict[str, Socket] = {}
        self._dirty: bool = True
        self._version: int = 0
        self._props: dict[str, Any] = {}
        self._setup_sockets()

    # -- abstract hooks -----------------------------------------------------

    @abstractmethod
    def _setup_sockets(self) -> None:
        """Declare input and output sockets for this node."""

    @abstractmethod
    def evaluate(self) -> None:
        """Read from inputs, process, and write to outputs."""

    # -- socket helpers -----------------------------------------------------

    def _add_input(self, name: str, stype: SocketType) -> Socket:
        """Create, register, and return a new input socket."""
        sock = Socket(name=name, socket_type=stype, is_output=False, node=self)
        self.inputs[name] = sock
        return sock

    def _add_output(self, name: str, stype: SocketType) -> Socket:
        """Create, register, and return a new output socket."""
        sock = Socket(name=name, socket_type=stype, is_output=True, node=self)
        self.outputs[name] = sock
        return sock

    # -- property accessors -------------------------------------------------

    def get_prop(self, key: str, default: Any = None) -> Any:
        """Return a node property, or *default* if not set."""
        return self._props.get(key, default)

    def set_prop(self, key: str, value: Any) -> None:
        """Set a node property and mark the node dirty if the value changed."""
        old = self._props.get(key)
        if old != value:
            self._props[key] = value
            self.mark_dirty()

    # -- dirty tracking -----------------------------------------------------

    def mark_dirty(self) -> None:
        """Flag this node (and increment its version) as needing re-evaluation."""
        if not self._dirty:
            self._dirty = True
            self._version += 1

    @property
    def is_dirty(self) -> bool:
        """Return whether this node needs re-evaluation."""
        return self._dirty

    def mark_clean(self) -> None:
        """Clear the dirty flag after successful evaluation."""
        self._dirty = False

    # -- dunder -------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(name={self.name!r}, "
            f"dirty={self._dirty}, version={self._version})"
        )


# ---------------------------------------------------------------------------
# Concrete nodes
# ---------------------------------------------------------------------------

class ImageInputNode(BaseNode):
    """Reads a :class:`ImageDataBlock` by name and presents it as an output.

    Properties:
        source (str): Name of the registered :class:`ImageDataBlock` to read.
    """

    node_type: str = "image_input"

    def _setup_sockets(self) -> None:
        self._add_output("image", SocketType.IMAGE)

    def evaluate(self) -> None:
        from image_splitter.engine.data_blocks import ImageDataBlock

        source_name: Optional[str] = self.get_prop("source")
        if source_name is None:
            self.outputs["image"].value = None
            return
        block = ImageDataBlock.get_by_name(source_name)
        if block is not None and block.image is not None:
            self.outputs["image"].value = block.image.copy()
        else:
            self.outputs["image"].value = None


class ImageOutputNode(BaseNode):
    """Writes the received image into a named :class:`ImageDataBlock`.

    Properties:
        target (str): Name under which to register / update the output block.
    """

    node_type: str = "image_output"

    def _setup_sockets(self) -> None:
        self._add_input("image", SocketType.IMAGE)

    def evaluate(self) -> None:
        from image_splitter.engine.data_blocks import ImageDataBlock

        target_name: Optional[str] = self.get_prop("target")
        img = self.inputs["image"].value
        if target_name is None or img is None:
            return
        block = ImageDataBlock.get_by_name(target_name)
        if block is not None:
            block.image = img.copy()
        else:
            ImageDataBlock(name=target_name, image=img.copy())


class ColorAdjustNode(BaseNode):
    """Apply brightness / contrast / sharpness / color enhancements.

    Properties:
        brightness (float): Brightness factor (default 1.0).
        contrast (float):   Contrast factor (default 1.0).
        sharpness (float):  Sharpness factor (default 1.0).
        color (float):      Color saturation factor (default 1.0).
    """

    node_type: str = "color_adjust"

    def _setup_sockets(self) -> None:
        self._add_input("image", SocketType.IMAGE)
        self._add_output("image", SocketType.IMAGE)

    def evaluate(self) -> None:
        img = self.inputs["image"].value
        if img is None:
            self.outputs["image"].value = None
            return

        result = img.copy()

        brightness = self.get_prop("brightness", 1.0)
        contrast = self.get_prop("contrast", 1.0)
        sharpness = self.get_prop("sharpness", 1.0)
        color = self.get_prop("color", 1.0)

        def _close_prev(prev, current):
            if prev is not current:
                prev.close()

        if brightness != 1.0:
            prev = result
            result = ImageEnhance.Brightness(result).enhance(brightness)
            _close_prev(prev, result)
        if contrast != 1.0:
            prev = result
            result = ImageEnhance.Contrast(result).enhance(contrast)
            _close_prev(prev, result)
        if sharpness != 1.0:
            prev = result
            result = ImageEnhance.Sharpness(result).enhance(sharpness)
            _close_prev(prev, result)
        if color != 1.0:
            prev = result
            result = ImageEnhance.Color(result).enhance(color)
            _close_prev(prev, result)

        self.outputs["image"].value = result


class BlendNode(BaseNode):
    """Blend two images together using :meth:`PIL.Image.blend`.

    Properties:
        opacity (float): Blend alpha (default 0.5).
    """

    node_type: str = "blend"

    def _setup_sockets(self) -> None:
        self._add_input("image_a", SocketType.IMAGE)
        self._add_input("image_b", SocketType.IMAGE)
        self._add_output("image", SocketType.IMAGE)

    def evaluate(self) -> None:
        img_a = self.inputs["image_a"].value
        img_b = self.inputs["image_b"].value
        if img_a is None or img_b is None:
            self.outputs["image"].value = img_a if img_a is not None else img_b
            return

        # L-3: coerce and clamp opacity into [0, 1] — out-of-range values
        # made Image.blend produce garbage or raise a cryptic error.
        try:
            opacity = float(self.get_prop("opacity", 0.5))
        except (TypeError, ValueError):
            opacity = 0.5
        opacity = min(1.0, max(0.0, opacity))

        # Ensure both images share the same mode and size.  `converted`
        # tracks the newest derived image we own; earlier derived images
        # are closed as soon as they are superseded.
        converted: Any = None
        if img_a.mode != img_b.mode:
            converted = img_b.convert(img_a.mode)
            img_b = converted
        if img_a.size != img_b.size:
            resized = img_b.resize(img_a.size)
            if converted is not None and converted is not img_b:
                converted.close()
            converted = resized
            img_b = converted

        blended = Image.blend(img_a, img_b, opacity)
        if converted is not None:
            converted.close()
        self.outputs["image"].value = blended
