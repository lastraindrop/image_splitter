"""Tests for error paths."""

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from image_splitter.core import process_image, register_all_processors


class TestErrorPaths(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        register_all_processors()

    def setUp(self):
        self._temp_dir_obj = tempfile.TemporaryDirectory()
        self.test_dir = Path(self._temp_dir_obj.name)
        self.output_dir = self.test_dir / "output"
        self.output_dir.mkdir(exist_ok=True)
        self.img_path = self.test_dir / "sample.png"
        Image.new("RGB", (20, 20), color="red").save(self.img_path)

    def tearDown(self):
        self._temp_dir_obj.cleanup()

    def test_missing_input_file_returns_fail(self):
        success, msg = process_image(str(self.test_dir / "missing.png"), "grid_splitter", {
            "rows": 1,
            "cols": 1,
            "output_dir": str(self.output_dir),
        })
        self.assertFalse(success)
        self.assertIn("File not found", msg)

    def test_invalid_template_placeholder_returns_fail(self):
        success, msg = process_image(str(self.img_path), "grid_splitter", {
            "rows": 1,
            "cols": 1,
            "output_dir": str(self.output_dir),
            "template": "{filename}_{not_exists}",
        })
        self.assertFalse(success)
        self.assertIn("Invalid template placeholder", msg)

    def test_invalid_enum_value_returns_fail(self):
        success, msg = process_image(str(self.img_path), "format_converter", {
            "format": "NOT_A_REAL_FORMAT",
            "quality": 90,
            "output_dir": str(self.output_dir),
        })
        self.assertFalse(success)
        self.assertIn("requires enum", msg)

    def test_invalid_list_value_returns_fail(self):
        success, msg = process_image(str(self.img_path), "custom_splitter", {
            "h_lines": "bad-list",
            "v_lines": [10],
            "output_dir": str(self.output_dir),
        })
        self.assertFalse(success)
        self.assertIn("requires list", msg)


if __name__ == "__main__":
    unittest.main()
