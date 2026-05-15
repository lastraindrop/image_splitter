# image_splitter/tests/test_edge_cases.py
"""Edge case tests for all processors and core pipeline."""
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from image_splitter.core import process_image, register_all_processors
from image_splitter.models import SplitConfig, ResizeConfig
from image_splitter.engine.registry import ProcessorRegistry


class TestProcessorEdgeCases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        register_all_processors()

    def setUp(self):
        self._temp_dir_obj = tempfile.TemporaryDirectory()
        self.test_dir = Path(self._temp_dir_obj.name).resolve()
        self.output_dir = self.test_dir / "output"
        self.output_dir.mkdir(exist_ok=True)

    def tearDown(self):
        self._temp_dir_obj.cleanup()

    def test_grid_splitter_1x1_returns_single_image(self):
        img_path = self.test_dir / "test.png"
        Image.new("RGB", (100, 100)).save(img_path)
        success, msg = process_image(str(img_path), "grid_splitter",
                                     {"rows": 1, "cols": 1, "output_dir": str(self.output_dir)})
        self.assertTrue(success, msg)
        self.assertEqual(len(list(self.output_dir.glob("*"))), 1)

    def test_resizer_ratio_1_produces_same_size(self):
        img_path = self.test_dir / "test.png"
        Image.new("RGB", (100, 100)).save(img_path)
        success, msg = process_image(str(img_path), "resizer",
                                     {"width": 1.0, "height": 1.0, "output_dir": str(self.output_dir)})
        self.assertTrue(success, msg)
        out = next(self.output_dir.glob("*"))
        with Image.open(out) as img:
            self.assertEqual(img.size, (100, 100))

    def test_resizer_very_small_ratio(self):
        img_path = self.test_dir / "test.png"
        Image.new("RGB", (100, 100)).save(img_path)
        success, msg = process_image(str(img_path), "resizer",
                                     {"width": 0.01, "height": 0.01, "output_dir": str(self.output_dir)})
        self.assertTrue(success, msg)

    def test_custom_splitter_single_h_line(self):
        img_path = self.test_dir / "test.png"
        Image.new("RGB", (100, 100)).save(img_path)
        success, msg = process_image(str(img_path), "custom_splitter",
                                     {"h_lines": [50], "v_lines": [], "output_dir": str(self.output_dir)})
        self.assertTrue(success, msg)
        self.assertEqual(len(list(self.output_dir.glob("*"))), 2)

    def test_canvas_adjuster_with_transparency(self):
        img_path = self.test_dir / "rgba.png"
        Image.new("RGBA", (100, 100), (255, 0, 0, 128)).save(img_path)
        success, msg = process_image(str(img_path), "canvas_adjuster",
                                     {"width": 200, "height": 200, "anchor": "center",
                                      "bg_color": [0, 0, 0, 0], "output_dir": str(self.output_dir)})
        self.assertTrue(success, msg)

    def test_filters_grayscale_and_invert_combined(self):
        img_path = self.test_dir / "test.png"
        Image.new("RGB", (50, 50), (128, 64, 32)).save(img_path)
        success, msg = process_image(str(img_path), "filters",
                                     {"grayscale": True, "invert": True, "output_dir": str(self.output_dir)})
        self.assertTrue(success, msg)

    def test_format_converter_webp_quality(self):
        img_path = self.test_dir / "test.png"
        Image.new("RGB", (100, 100)).save(img_path)
        success, msg = process_image(str(img_path), "format_converter",
                                     {"format": "WebP", "quality": 50, "output_dir": str(self.output_dir)})
        self.assertTrue(success, msg)
        out = next(self.output_dir.glob("*.webp"))
        self.assertTrue(out.exists())

    def test_geometry_flip_only(self):
        img_path = self.test_dir / "test.png"
        Image.new("RGB", (100, 100)).save(img_path)
        success, msg = process_image(str(img_path), "geometry",
                                     {"rotate": "0", "flip_h": True, "flip_v": False,
                                      "output_dir": str(self.output_dir)})
        self.assertTrue(success, msg)

    def test_metadata_cleaner_strip_false(self):
        img_path = self.test_dir / "test.png"
        Image.new("RGB", (50, 50)).save(img_path)
        success, msg = process_image(str(img_path), "metadata_cleaner",
                                     {"strip_all": False, "keep_icc": True,
                                      "output_dir": str(self.output_dir)})
        self.assertTrue(success, msg)

    def test_color_adjuster_all_default(self):
        img_path = self.test_dir / "test.png"
        Image.new("RGB", (50, 50)).save(img_path)
        success, msg = process_image(str(img_path), "color_adjuster",
                                     {"brightness": 1.0, "contrast": 1.0, "sharpness": 1.0,
                                      "color": 1.0, "output_dir": str(self.output_dir)})
        self.assertTrue(success, msg)

    def test_watermark_empty_text(self):
        img_path = self.test_dir / "test.png"
        Image.new("RGB", (100, 100)).save(img_path)
        success, msg = process_image(str(img_path), "text_watermark",
                                     {"text": "", "output_dir": str(self.output_dir)})
        self.assertTrue(success, msg)

    def test_watermark_on_palette_mode(self):
        img_path = self.test_dir / "palette.png"
        img = Image.new("P", (50, 50))
        img.putpalette([i % 256 for i in range(768)])
        img.save(img_path)
        success, msg = process_image(str(img_path), "text_watermark",
                                     {"text": "P", "output_dir": str(self.output_dir)})
        self.assertTrue(success, msg)

    def test_grid_splitter_large_offset(self):
        img_path = self.test_dir / "test.png"
        Image.new("RGB", (100, 100)).save(img_path)
        success, msg = process_image(str(img_path), "grid_splitter",
                                     SplitConfig(rows=1, cols=1, offsets=(49, 49, 49, 49),
                                                 output_dir=str(self.output_dir)))
        self.assertTrue(success, msg)

    def test_config_model_validation_rejects_bad_rows(self):
        with self.assertRaises(ValueError):
            SplitConfig(rows=0, cols=1, output_dir=str(self.output_dir))

    def test_resize_config_rejects_negative(self):
        with self.assertRaises(ValueError):
            ResizeConfig(width=-1.0, height=1.0)

    def test_process_nonexistent_file(self):
        success, msg = process_image("/nonexistent.png", "grid_splitter",
                                     {"rows": 1, "cols": 1, "output_dir": str(self.output_dir)})
        self.assertFalse(success)
        self.assertIn("File not found", msg)

    def test_process_unknown_processor(self):
        img_path = self.test_dir / "test.png"
        Image.new("RGB", (50, 50)).save(img_path)
        with self.assertRaises(ValueError):
            ProcessorRegistry.get("nonexistent_processor")


if __name__ == "__main__":
    unittest.main()
