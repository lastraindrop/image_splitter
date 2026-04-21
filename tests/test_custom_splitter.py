# image_splitter/tests/test_custom_splitter.py
import unittest
import tempfile
from PIL import Image
from pathlib import Path
from image_splitter.models import CustomSplitConfig
from image_splitter.core import process_image

class TestCustomSplitter(unittest.TestCase):
    def setUp(self):
        self._temp_dir_obj = tempfile.TemporaryDirectory()
        self.test_dir = Path(self._temp_dir_obj.name).resolve()
        self.output_dir = self.test_dir / "output"
        self.output_dir.mkdir(exist_ok=True)
        
        # Create a 100x100 test image
        self.img_path = self.test_dir / "test_100.png"
        Image.new("RGB", (100, 100), color="white").save(self.img_path)

    def tearDown(self):
        self._temp_dir_obj.cleanup()

    def test_custom_split_simple(self):
        """Test simple cross split (2x2)."""
        # Cut once at 50 on each axis
        config = CustomSplitConfig(
            h_lines=[50], 
            v_lines=[50], 
            output_dir=str(self.output_dir),
            template="{filename}_{row}_{col}"
        )
        
        success, msg = process_image(str(self.img_path), "custom_splitter", config)
        self.assertTrue(success, msg)
        
        # Verify files
        files = list(self.output_dir.glob("*.png"))
        self.assertEqual(len(files), 4)
        
        # Verify top-left block is 50x50
        with Image.open(self.output_dir / "test_100_1_1.png") as img:
            self.assertEqual(img.size, (50, 50))

    def test_custom_split_irregular(self):
        """Test irregular coordinate split."""
        # Y-axis cut points: 20, 80 -> intervals (0,20), (20,80), (80,100) -> 3 rows
        # X-axis cut points: 30 -> intervals (0,30), (30,100) -> 2 cols
        # Total 3x2 = 6 blocks
        config = CustomSplitConfig(
            h_lines=[20, 80],
            v_lines=[30],
            output_dir=str(self.output_dir)
        )
        
        success, _ = process_image(str(self.img_path), "custom_splitter", config)
        self.assertTrue(success)
        
        files = list(self.output_dir.glob("*.png"))
        self.assertEqual(len(files), 6)

    def test_custom_split_out_of_bounds(self):
        """Test out-of-bounds lines are ignored."""
        config = CustomSplitConfig(
            h_lines=[150], # Beyond 100
            v_lines=[50],
            output_dir=str(self.output_dir)
        )
        
        success, _ = process_image(str(self.img_path), "custom_splitter", config)
        self.assertTrue(success)
        # Generates 1x2 = 2 blocks
        files = list(self.output_dir.glob("*.png"))
        self.assertEqual(len(files), 2)

    def test_custom_split_negative_forbidden(self):
        """Test negative lines are intercepted by the model."""
        with self.assertRaises(ValueError) as ctx:
            CustomSplitConfig(
                h_lines=[-10],
                v_lines=[50],
                output_dir=str(self.output_dir)
            )
        self.assertIn("non-negative integers", str(ctx.exception))

if __name__ == '__main__':
    unittest.main()
