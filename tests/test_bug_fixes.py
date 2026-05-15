# image_splitter/tests/test_bug_fixes.py
"""Verification tests for all confirmed bug fixes."""
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from image_splitter.core import process_image, register_all_processors
from image_splitter.engine.registry import ProcessorRegistry
from image_splitter.models import ResizeConfig


class TestBugFixes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        register_all_processors()

    def setUp(self):
        self._temp_dir_obj = tempfile.TemporaryDirectory()
        self.test_dir = Path(self._temp_dir_obj.name).resolve()
        self.output_dir = self.test_dir / "output"
        self.output_dir.mkdir(exist_ok=True)
        self.img_path = self.test_dir / "test.png"
        Image.new("RGB", (100, 100), color="red").save(self.img_path)
        self.rgba_path = self.test_dir / "test_rgba.png"
        Image.new("RGBA", (100, 100), color=(255, 0, 0, 128)).save(self.rgba_path)

    def tearDown(self):
        self._temp_dir_obj.cleanup()

    def test_bug01_watermark_returns_result(self):
        """BUG-01: watermark process() must return List[Tuple[Image, Dict]]."""
        config = {
            "text": "TEST",
            "opacity": 128,
            "size": 20,
            "anchor": "BR",
            "output_dir": str(self.output_dir),
        }
        success, msg = process_image(str(self.rgba_path), "text_watermark", config)
        self.assertTrue(success, f"Watermark processing failed: {msg}")
        files = list(self.output_dir.glob("*.png"))
        self.assertGreater(len(files), 0)

    def test_bug01_watermark_produces_rgba_output(self):
        """Watermark output must preserve alpha channel."""
        config = {
            "text": "WATERMARK",
            "opacity": 200,
            "anchor": "C",
            "output_dir": str(self.output_dir),
            "template": "wm_test",
        }
        success, msg = process_image(str(self.rgba_path), "text_watermark", config)
        self.assertTrue(success, msg)
        with Image.open(self.output_dir / "wm_test.png") as img:
            self.assertEqual(img.mode, "RGBA")

    def test_bug02_resizer_config_model_rejects_zero(self):
        """ResizeConfig must reject zero or negative ratios (Fail-Fast)."""
        with self.assertRaises(ValueError):
            ResizeConfig(width=0, height=1.0)
        with self.assertRaises(ValueError):
            ResizeConfig(width=1.0, height=-0.5)
        with self.assertRaises(ValueError):
            ResizeConfig(width=0.0, height=0.0)

    def test_bug02_resizer_valid_config_passes(self):
        """Valid resize config should pass validation."""
        config = ResizeConfig(width=0.5, height=2.0)
        self.assertEqual(config.width, 0.5)
        self.assertEqual(config.height, 2.0)

    def test_bug03_geometry_rejects_invalid_angle(self):
        """geometry processor must reject non-standard rotation angles."""
        config = {
            "rotate": "45",
            "flip_h": False,
            "flip_v": False,
            "output_dir": str(self.output_dir),
        }
        success, msg = process_image(str(self.img_path), "geometry", config)
        self.assertFalse(success)
        self.assertTrue(
            "Unsupported rotation angle" in msg or "requires enum" in msg,
            f"Expected rejection of angle 45, got: {msg}"
        )

    def test_bug03_geometry_accepts_standard_angles(self):
        """geometry processor must accept 0/90/180/270."""
        for angle in ["0", "90", "180", "270"]:
            with self.subTest(angle=angle):
                out_sub = self.output_dir / angle
                out_sub.mkdir(exist_ok=True)
                config = {
                    "rotate": angle,
                    "output_dir": str(out_sub),
                    "template": f"rot_{angle}",
                }
                success, msg = process_image(str(self.img_path), "geometry", config)
                self.assertTrue(success, f"Angle {angle} failed: {msg}")

    def test_bug04_processors_init_exports_all(self):
        """All 10 processors must be importable from processors package."""
        from image_splitter.processors import (
            GridSplitter, ImageResizer, CustomLineSplitter, CanvasAdjuster,
            ImageColorAdjuster, SimpleFilterProcessor, ImageFormatConverter,
            GeometryProcessor, MetadataProcessor, TextWatermark,
        )
        classes = [
            GridSplitter, ImageResizer, CustomLineSplitter, CanvasAdjuster,
            ImageColorAdjuster, SimpleFilterProcessor, ImageFormatConverter,
            GeometryProcessor, MetadataProcessor, TextWatermark,
        ]
        self.assertEqual(len(classes), 10)

    def test_bug05_metadata_palette_mode_handling(self):
        """metadata_cleaner must handle P-mode images without color corruption."""
        img = Image.new("P", (50, 50))
        palette = [i % 256 for i in range(768)]
        img.putpalette(palette)
        p_path = self.test_dir / "palette.png"
        img.save(p_path)

        config = {
            "strip_all": True,
            "keep_icc": False,
            "output_dir": str(self.output_dir),
            "template": "palette_clean",
        }
        success, msg = process_image(str(p_path), "metadata_cleaner", config)
        self.assertTrue(success, msg)

    def test_bug06_cli_set_type_coercion(self):
        """CLI --set values must be coerced to correct types via processor metadata."""
        processor = ProcessorRegistry.get("grid_splitter")
        from image_splitter.engine.config_coercion import coerce_processor_config
        raw = {"rows": "3", "cols": "2"}
        coerced = coerce_processor_config(processor, raw)
        self.assertIsInstance(coerced["rows"], int)
        self.assertIsInstance(coerced["cols"], int)
        self.assertEqual(coerced["rows"], 3)
        self.assertEqual(coerced["cols"], 2)

    def test_bug07_watermark_all_anchors_produce_output(self):
        """Watermark must work for all 5 anchor positions."""
        for anchor in ["TL", "TR", "BL", "BR", "C"]:
            with self.subTest(anchor=anchor):
                out_sub = self.output_dir / anchor
                out_sub.mkdir(exist_ok=True)
                config = {
                    "text": f"WM_{anchor}",
                    "anchor": anchor,
                    "opacity": 128,
                    "output_dir": str(out_sub),
                    "template": f"wm_{anchor}",
                }
                success, msg = process_image(str(self.rgba_path), "text_watermark", config)
                self.assertTrue(success, f"Anchor {anchor} failed: {msg}")


if __name__ == "__main__":
    unittest.main()
