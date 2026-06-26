"""Tests for new processors: rounded_corner, border, smart_crop."""

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from image_splitter.core import process_image, register_all_processors


class TestNewProcessors(unittest.TestCase):
    """Smoke and edge-case tests for the 3 new processors."""

    @classmethod
    def setUpClass(cls):
        register_all_processors()

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.test_dir = Path(self._tmp.name)
        self.out_dir = self.test_dir / "output"
        self.out_dir.mkdir()
        self.img_path = self.test_dir / "test.png"
        Image.new("RGB", (200, 200), "blue").save(self.img_path)
        self.rgba_path = self.test_dir / "test_rgba.png"
        Image.new("RGBA", (200, 200), (255, 0, 0, 200)).save(self.rgba_path)

    def tearDown(self):
        self._tmp.cleanup()

    # ── Rounded Corner ──────────────────────────────────────────────

    def test_rounded_corner_default(self):
        success, msg = process_image(str(self.img_path), "rounded_corner", {
            "output_dir": str(self.out_dir), "template": "rc_default",
        })
        self.assertTrue(success, msg)
        out = self.out_dir / "rc_default.png"
        self.assertTrue(out.exists())
        with Image.open(out) as img:
            self.assertEqual(img.mode, "RGBA")

    def test_rounded_corner_radius_zero_clamped(self):
        """radius <= 0 should fail validation."""
        success, msg = process_image(str(self.img_path), "rounded_corner", {
            "radius": 0, "output_dir": str(self.out_dir), "template": "rc_zero",
        })
        self.assertFalse(success)

    def test_rounded_corner_large_radius_clamped(self):
        """Radius larger than image half-size should be clamped."""
        success, msg = process_image(str(self.img_path), "rounded_corner", {
            "radius": 500, "output_dir": str(self.out_dir), "template": "rc_large",
        })
        self.assertTrue(success, msg)
        out = self.out_dir / "rc_large.png"
        self.assertTrue(out.exists())

    # ── Border ──────────────────────────────────────────────────────

    def test_border_solid(self):
        success, msg = process_image(str(self.img_path), "border", {
            "width": 10, "color": "#ff0000", "style": "solid",
            "output_dir": str(self.out_dir), "template": "border_solid",
        })
        self.assertTrue(success, msg)
        out = self.out_dir / "border_solid.png"
        self.assertTrue(out.exists())
        with Image.open(out) as img:
            # Image should have grown by 2 * border width
            self.assertEqual(img.size, (220, 220))

    def test_border_dashed(self):
        success, msg = process_image(str(self.img_path), "border", {
            "width": 6, "color": "#00ff00", "style": "dashed",
            "output_dir": str(self.out_dir), "template": "border_dashed",
        })
        self.assertTrue(success, msg)

    def test_border_double(self):
        success, msg = process_image(str(self.img_path), "border", {
            "width": 12, "color": "#3b82f6", "style": "double",
            "output_dir": str(self.out_dir), "template": "border_double",
        })
        self.assertTrue(success, msg)

    def test_border_invalid_color(self):
        success, msg = process_image(str(self.img_path), "border", {
            "color": "red", "output_dir": str(self.out_dir), "template": "border_bad",
        })
        self.assertFalse(success)

    # ── Smart Crop ──────────────────────────────────────────────────

    def test_smart_crop_rgba(self):
        """RGBA image: crops to non-transparent region."""
        success, msg = process_image(str(self.rgba_path), "smart_crop", {
            "threshold": 30, "margin": 5,
            "output_dir": str(self.out_dir), "template": "sc_rgba",
        })
        self.assertTrue(success, msg)
        out = self.out_dir / "sc_rgba.png"
        self.assertTrue(out.exists())

    def test_smart_crop_rgb(self):
        """RGB image: uses luminance threshold."""
        success, msg = process_image(str(self.img_path), "smart_crop", {
            "threshold": 30, "margin": 10,
            "output_dir": str(self.out_dir), "template": "sc_rgb",
        })
        self.assertTrue(success, msg)

    def test_smart_crop_invalid_threshold(self):
        success, msg = process_image(str(self.img_path), "smart_crop", {
            "threshold": 300, "output_dir": str(self.out_dir), "template": "sc_bad",
        })
        self.assertFalse(success)


if __name__ == "__main__":
    unittest.main()
