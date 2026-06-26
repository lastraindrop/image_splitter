"""Tests for canvas adjuster."""

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from image_splitter.core import process_image
from image_splitter.models import AdjustConfig

class TestCanvasAdjuster(unittest.TestCase):
    def setUp(self):
        self._temp_dir_obj = tempfile.TemporaryDirectory()
        self.test_dir = Path(self._temp_dir_obj.name).resolve()
        self.output_dir = self.test_dir / "output"
        self.output_dir.mkdir(exist_ok=True)
        
        # Create a 100x100 red test image
        self.img_path = self.test_dir / "test_100.png"
        Image.new("RGB", (100, 100), color="red").save(self.img_path)

    def tearDown(self):
        self._temp_dir_obj.cleanup()

    def test_canvas_padding(self):
        """Test canvas padding."""
        # 100x100 -> 200x200, blue background, center
        config = AdjustConfig(
            width=200, height=200, 
            bg_color=(0, 0, 255), 
            output_dir=str(self.output_dir)
        )
        success, _ = process_image(str(self.img_path), "canvas_adjuster", config)
        self.assertTrue(success)
        
        save_path = self.output_dir / "test_100_adjusted.png"
        with Image.open(save_path) as img:
            self.assertEqual(img.size, (200, 200))
            # Verify background color (edge pixel should be blue)
            self.assertEqual(img.getpixel((0, 0)), (0, 0, 255))
            # Verify center pixel (center should be red)
            self.assertEqual(img.getpixel((100, 100)), (255, 0, 0))

    def test_canvas_cropping(self):
        """Test canvas cropping."""
        # 100x100 -> 50x50, crop from top-left
        config = AdjustConfig(
            width=50, height=50, 
            anchor="top-left",
            output_dir=str(self.output_dir)
        )
        success, _ = process_image(str(self.img_path), "canvas_adjuster", config)
        self.assertTrue(success)
        
        with Image.open(self.output_dir / "test_100_adjusted.png") as img:
            self.assertEqual(img.size, (50, 50))

    def test_canvas_ratio(self):
        """Test scaling canvas by ratio."""
        # 100x100 -> 1.5x width, 0.5x height (150x50)
        config = AdjustConfig(
            width=1.5, height=0.5,
            output_dir=str(self.output_dir)
        )
        success, _ = process_image(str(self.img_path), "canvas_adjuster", config)
        self.assertTrue(success)
        
        with Image.open(self.output_dir / "test_100_adjusted.png") as img:
            self.assertEqual(img.size, (150, 50))

    def test_adjust_config_fail_fast(self):
        """Invalid config should be intercepted directly at the model layer."""
        with self.assertRaises(ValueError):
            AdjustConfig(width=0, height=50, output_dir=str(self.output_dir))

if __name__ == '__main__':
    unittest.main()
