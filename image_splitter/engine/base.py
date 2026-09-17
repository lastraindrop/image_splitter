"""Base classes and interfaces for the image processing engine."""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image


class BaseProcessor(ABC):
    """Image processor plugin base class.

    All specific processors (e.g., grid splitters, resizers) must inherit from this class and implement the abstract methods.
    """
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier name for the processor (snake_case)."""
        pass
    @property
    @abstractmethod
    def display_name(self) -> str:
        """Name displayed in the GUI interface."""
        pass
    @property
    def category(self) -> str:
        """Category it belongs to.

        Optional values: 'Split', 'Transform', 'Edit', 'Filter', 'Export'.
        """
        return "Transform"
    @property
    def tool_tip(self) -> str:
        """Short description or tooltip for the operation."""
        return ""
    @property
    def config_model(self) -> Optional[type]:
        """Configuration validation model class (DataClass) corresponding to this processor."""
        return None
    @abstractmethod
    def process(
        self,
        image: Image.Image,
        config: Dict[str, Any]
    ) -> List[Tuple[Image.Image, Dict[str, Any]]]:
        """Core processing logic.
        Args:
            image: Input PIL image object.
            config: Configuration dictionary after cleaning and type conversion.
        Returns:
            List of processing results. Each element is a tuple (Image, Context),
            where Context is used for placeholder replacement in naming templates.
        """
        pass
    def get_ui_metadata(self) -> List[Dict[str, Any]]:
        """Define parameter metadata required for automatic UI generation.
        When ``config_model`` is set to a dataclass whose fields carry
        ``field(metadata={"label": ...})`` annotations, the metadata is
        auto-generated via :func:`~engine._ui_metadata_util.ui_metadata_from_dataclass`.
        Override this method only for processors whose UI representation
        differs from the dataclass schema (e.g. different types or enum options).
        Returns:
            List of parameter definitions compatible with ``config_coercion``.
        """
        if self.config_model is not None:
            from image_splitter.engine._ui_metadata_util import (
                ui_metadata_from_dataclass,
            )
            return ui_metadata_from_dataclass(self.config_model)
        return []
    def draw_preview(
        self,
        canvas: Any,
        thumb_size: Tuple[int, int],
        canvas_pos: Tuple[int, int],
        ratio: float,
        props: Dict[str, Any],
        theme: Any
    ) -> None:
        """Draw preview auxiliary lines or overlays on the GUI canvas.
        Args:
            canvas: tkinter.Canvas object.
            thumb_size: Actual size of the thumbnail on the canvas (w, h).
            canvas_pos: Coordinates of the thumbnail's top-left corner on the canvas (x, y).
            ratio: Scaling ratio from the original image to the thumbnail.
            props: Variable dictionary of current UI controls.
            theme: UI theme configuration object.
        """
        pass
