"""Shared test fixtures and utilities for the image_splitter test suite.

Provides auto-adapting fixtures that avoid hardcoding processor counts,
image sizes, or file paths. All tests should use these fixtures to
stay in sync with architecture changes.
"""
import tempfile
import unittest
from pathlib import Path
from typing import List, Tuple

from PIL import Image

from image_splitter import core
from image_splitter.engine.registry import ProcessorRegistry

# ---------------------------------------------------------------------------
# Color constants
# ---------------------------------------------------------------------------
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RGBA_SEMI_RED = (255, 0, 0, 128)
RGBA_TRANSPARENT = (0, 0, 0, 0)

# ---------------------------------------------------------------------------
# Helper: create test images
# ---------------------------------------------------------------------------
def make_rgb_image(
    size: Tuple[int, int] = (100, 100),
    color: Tuple[int, int, int] = RED,
) -> Image.Image:
    return Image.new("RGB", size, color)


def make_rgba_image(
    size: Tuple[int, int] = (100, 100),
    color: Tuple[int, int, int, int] = RGBA_SEMI_RED,
) -> Image.Image:
    return Image.new("RGBA", size, color)


def make_palette_image(size: Tuple[int, int] = (50, 50)) -> Image.Image:
    img = Image.new("P", size)
    palette = [i % 256 for i in range(768)]
    img.putpalette(palette)
    return img


def make_grayscale_image(
    size: Tuple[int, int] = (100, 100), value: int = 128
) -> Image.Image:
    return Image.new("L", size, value)


def make_gradient_image(size: Tuple[int, int] = (100, 100)) -> Image.Image:
    """Create an RGB image with a simple gradient for pixel-accuracy tests."""
    img = Image.new("RGB", size)
    pixels = img.load()
    if pixels is None:
        return img
    w, h = size
    for y in range(h):
        for x in range(w):
            pixels[x, y] = (x % 256, y % 256, (x + y) % 256)
    return img


def assert_images_equal(a: Image.Image, b: Image.Image) -> None:
    """Assert two images have identical size, mode, and pixel data."""
    assert a.size == b.size
    assert a.mode == b.mode
    assert list(a.getdata()) == list(b.getdata())


# ---------------------------------------------------------------------------
# Helper: count registered processors (auto-adapting)
# ---------------------------------------------------------------------------
def processor_count() -> int:
    return len(ProcessorRegistry.list_all())


def get_processor_names() -> List[str]:
    return sorted(p.name for p in ProcessorRegistry.list_all())


# ---------------------------------------------------------------------------
# Base test class with auto-fixtures
# ---------------------------------------------------------------------------
class BaseTest(unittest.TestCase):
    """Base test case with automatic temp directory, test images, and
    processor registration. Subclass this instead of unittest.TestCase."""

    @classmethod
    def setUpClass(cls) -> None:
        """Register all processors once per test class."""
        core.register_all_processors()

    def setUp(self) -> None:
        """Create a temp directory and standard test images."""
        self._temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self._temp_dir.name).resolve()
        self.output_dir = self.test_dir / "output"
        self.output_dir.mkdir(exist_ok=True)

        self.img_rgb = make_rgb_image()
        self.img_rgba = make_rgba_image()
        self.img_palette = make_palette_image()
        self.img_gray = make_grayscale_image()

        self.rgb_path = self.test_dir / "test.png"
        self.rgba_path = self.test_dir / "test_rgba.png"
        self.palette_path = self.test_dir / "test_p.png"
        self.gray_path = self.test_dir / "test_l.png"

        self.img_rgb.save(self.rgb_path)
        self.img_rgba.save(self.rgba_path)
        self.img_palette.save(self.palette_path)
        self.img_gray.save(self.gray_path)

    def tearDown(self) -> None:
        """Clean up temp directory."""
        self._temp_dir.cleanup()

    def sub_output_dir(self, name: str) -> Path:
        """Create and return a named subdirectory of output_dir."""
        d = self.output_dir / name
        d.mkdir(exist_ok=True)
        return d

    def count_output_files(self, subdir: str | None = None) -> int:
        """Count files in the output dir (or its subdir)."""
        d = self.output_dir / subdir if subdir else self.output_dir
        return len(list(d.glob("*"))) if d.exists() else 0

    def output_files(self, subdir: str | None = None) -> List[Path]:
        """List files in the output dir (or its subdir)."""
        d = self.output_dir / subdir if subdir else self.output_dir
        return sorted(d.glob("*")) if d.exists() else []

    def assert_processor(
        self, name: str, config: dict, *, expect_fail: bool = False
    ) -> tuple:
        """Run process_image with standard rgb_path and assert result.

        Returns the (success, message) tuple.
        """
        config = {**config, "output_dir": str(self.output_dir)}
        from image_splitter.core import process_image

        success, msg = process_image(str(self.rgb_path), name, config)
        if not expect_fail:
            self.assertTrue(success, f"{name} failed: {msg}")
        return success, msg


class TkTestCase(unittest.TestCase):
    """Base class for customtkinter tests with headless-safe skipping.

    Set ``register_processors = True`` when widgets depend on the processor
    registry. Set ``map_offscreen = True`` for tests that need real key/focus
    events; withdrawn windows do not reliably dispatch those events.
    """

    register_processors = False
    map_offscreen = False

    def setUp(self) -> None:
        if self.register_processors:
            core.register_all_processors()
        try:
            import customtkinter as ctk
            self.root = ctk.CTk()
        except Exception:
            self.skipTest("Tk environment unavailable")
        if self.map_offscreen:
            self.root.geometry("+10000+10000")
            self.root.update()
        else:
            self.root.withdraw()

    def tearDown(self) -> None:
        if hasattr(self, "root"):
            self.root.destroy()
