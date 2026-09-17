"""ImageDataBlock — named, versioned, reference-counted image data container.

Inspired by Blender's ID datablock system.  Each block wraps a PIL Image
with metadata, version tracking, and a class-level name registry so that
consumers (e.g. the Node Graph evaluator) can look up image data by name
and detect mutations via the monotonically-increasing version counter.
"""

from __future__ import annotations

import threading
from typing import Any, Optional

from PIL import Image


class ImageDataBlock:
    """Named, versioned, reference-counted container for PIL Image data.

    Attributes:
        name: Unique human-readable identifier used as the registry key.
        users: Reference count.  When it drops to zero the image data is
            released automatically via :meth:`unuse`.
    """

    # Class-level name registry: name -> ImageDataBlock
    _name_registry: dict[str, "ImageDataBlock"] = {}
    _registry_lock: threading.Lock = threading.Lock()

    def __init__(
        self,
        name: str,
        image: Optional[Image.Image] = None,
        source_path: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Initialise a new ImageDataBlock and register it.

        Args:
            name: Unique name for this block.  If the name already exists in
                the registry the previous entry is silently replaced.
            image: Optional PIL Image to hold.
            source_path: Optional filesystem path the image was loaded from.
            metadata: Optional pre-built metadata dict.  When *image* is
                provided the block will also extract metadata directly from
                the PIL Image object (ICC profile, EXIF, DPI).
        """
        self._name: str = name
        self._image: Optional[Image.Image] = image
        self._source_path: Optional[str] = source_path
        self._version: int = 0
        self._metadata: dict[str, Any] = dict(metadata) if metadata else {}
        self.users: int = 0

        if image is not None:
            self._extract_image_metadata()

        # Release previous block with the same name to prevent memory leaks
        with ImageDataBlock._registry_lock:
            old_block = ImageDataBlock._name_registry.get(name)
            if old_block is not None and old_block is not self:
                old_block.release()
            ImageDataBlock._name_registry[name] = self

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        """Return the block name."""
        return self._name

    @property
    def image(self) -> Optional[Image.Image]:
        """Return the wrapped PIL Image (may be ``None``)."""
        return self._image

    @image.setter
    def image(self, value: Optional[Image.Image]) -> None:
        """Replace the held image, bump version, and extract metadata.

        Args:
            value: A PIL Image or ``None`` to clear the image.
        """
        # P1-10: Close previous image to prevent resource leaks.
        if self._image is not None and self._image is not value:
            try:
                self._image.close()
            except Exception:
                pass
        self._image = value
        self._version += 1
        if value is not None:
            self._extract_image_metadata()

    @property
    def version(self) -> int:
        """Return the current version number (read-only).

        The version is incremented on every image mutation so that
        downstream consumers can use ``(name, version)`` as a cache key.
        """
        return self._version

    @property
    def source_path(self) -> Optional[str]:
        """Return the filesystem path the image was loaded from."""
        return self._source_path

    @source_path.setter
    def source_path(self, value: Optional[str]) -> None:
        self._source_path = value

    @property
    def metadata(self) -> dict[str, Any]:
        """Return the metadata dict (mutable reference)."""
        return self._metadata

    @property
    def size(self) -> tuple[int, int]:
        """Return ``(width, height)`` or ``(0, 0)`` if no image."""
        if self._image is not None:
            return self._image.size
        return (0, 0)

    @property
    def is_loaded(self) -> bool:
        """Return ``True`` if an image is currently held."""
        return self._image is not None

    # ------------------------------------------------------------------
    # Metadata extraction
    # ------------------------------------------------------------------

    def _extract_image_metadata(self) -> None:
        """Pull ICC profile, EXIF, and DPI from the current PIL Image.

        Existing keys in ``_metadata`` are preserved unless overwritten by
        values found in ``image.info``.
        """
        if self._image is None:
            return

        info = self._image.info
        for key in ("icc_profile", "exif", "dpi"):
            if key in info:
                self._metadata[key] = info[key]

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------

    def touch(self) -> None:
        """Bump the version counter without changing image content.

        Useful for forcing cache invalidation in downstream consumers.
        """
        self._version += 1

    # ------------------------------------------------------------------
    # Reference counting
    # ------------------------------------------------------------------

    def use(self) -> None:
        """Increment the reference count."""
        self.users += 1

    def unuse(self) -> None:
        """Decrement the reference count.

        When the count reaches zero the underlying PIL Image is released
        automatically to free memory.
        """
        self.users = max(0, self.users - 1)
        if self.users == 0:
            self.release()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def clone(self, new_name: str) -> ImageDataBlock:
        """Create a shallow copy with a new name and a fresh version.

        The PIL Image is duplicated via ``.copy()`` so that pixel changes
        to the clone do not affect the original.

        Args:
            new_name: Name for the cloned block.

        Returns:
            A new :class:`ImageDataBlock` registered under *new_name*.
        """
        copied_image = self._image.copy() if self._image is not None else None
        cloned = ImageDataBlock(
            name=new_name,
            image=copied_image,
            source_path=self._source_path,
            metadata=dict(self._metadata),
        )
        return cloned

    def release(self) -> None:
        """Close the PIL Image and clear the reference to free memory."""
        if self._image is not None:
            self._image.close()
            self._image = None

    # ------------------------------------------------------------------
    # Class-level registry helpers
    # ------------------------------------------------------------------

    @classmethod
    def get_by_name(cls, name: str) -> Optional[ImageDataBlock]:
        """Look up a block by its registered name.

        Args:
            name: The block name to search for.

        Returns:
            The matching :class:`ImageDataBlock`, or ``None`` if not found.
        """
        with cls._registry_lock:
            return cls._name_registry.get(name)

    @classmethod
    def forget(cls, name: str, *, close_image: bool = True) -> None:
        """Remove a block from the registry and optionally release its image.

        Args:
            name: The block name to remove.
            close_image: When ``True`` (default) the wrapped image is
                closed.  Pass ``False`` to transfer ownership of the
                image back to the caller — used when a block merely
                *borrows* an image it does not own (e.g. the unified
                execution path borrows the caller's image).
        """
        with cls._registry_lock:
            block = cls._name_registry.pop(name, None)
        if block is not None and close_image:
            block.release()

    @classmethod
    def list_all(cls) -> list[ImageDataBlock]:
        """Return a list of all currently registered blocks."""
        with cls._registry_lock:
            return list(cls._name_registry.values())

    @classmethod
    def clear_all(cls) -> None:
        """Release every registered block and clear the registry."""
        with cls._registry_lock:
            blocks = list(cls._name_registry.values())
            cls._name_registry.clear()
        for block in blocks:
            block.release()

    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"ImageDataBlock(name={self._name!r}, "
            f"version={self._version}, "
            f"size={self.size}, "
            f"users={self.users})"
        )
