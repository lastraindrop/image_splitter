# image_splitter/tests/test_processors_expanded.py
import unittest
import tempfile
from PIL import Image
from pathlib import Path
from image_splitter.core import process_image, register_all_processors
from image_splitter.models import SplitConfig

class TestProcessorsDeepDive(unittest.TestCase):
    """
    Deep parameter adaptation and logical analysis for each processor (Rule 3)
    """
    
    @classmethod
    def setUpClass(cls):
        # Ensure all plugins are loaded
        register_all_processors()

    def setUp(self):
        self._temp_dir_obj = tempfile.TemporaryDirectory()
        self.test_dir = Path(self._temp_dir_obj.name).resolve()
        self.output_dir = self.test_dir / "output"
        self.output_dir.mkdir(exist_ok=True)
        
        # Create a 100x100 semi-transparent test image
        self.rgba_path = self.test_dir / "test_rgba.png"
        Image.new("RGBA", (100, 100), color=(255, 0, 0, 100)).save(self.rgba_path)

    def tearDown(self):
        self._temp_dir_obj.cleanup()

    def test_grid_splitter_rounding_consistency(self):
        """Rule 3: Boundary Point Analysis - Rounding consistency of 100 pixels divided by 3 (M3)"""
        config = SplitConfig(rows=1, cols=3, output_dir=str(self.output_dir))
        success, _ = process_image(str(self.rgba_path), "grid_splitter", config)
        self.assertTrue(success)
        
        tiles = sorted(self.output_dir.glob("*.png"))
        self.assertEqual(len(tiles), 3)
        
        # Verify if the total width remains unchanged (original image 100)
        total_w = 0
        for t in tiles:
            with Image.open(t) as img:
                total_w += img.width
        self.assertEqual(total_w, 100, f"Grid splitting caused pixel loss or overflow: {total_w} != 100")

    def test_watermark_positioning_and_opacity(self):
        """Rule 3: Adaptation Case - Watermark positioning in each quadrant and opacity overlay"""
        anchors = ["TL", "TR", "BL", "BR", "C"]
        for anchor in anchors:
            with self.subTest(anchor=anchor):
                config = {
                    "text": f"WD_{anchor}",
                    "opacity": 200,
                    "anchor": anchor,
                    "output_dir": str(self.output_dir),
                    "template": "{filename}_{anchor}"
                }
                success, msg = process_image(str(self.rgba_path), "text_watermark", config)
                self.assertTrue(success, f"Watermark processing failed [Anchor: {anchor}]: {msg}")
                
                # Verify that the generated file can be loaded (suffix specified in template or automatically added by process_image)
                try:
                    out_file = next(self.output_dir.glob(f"*_{anchor}.png"))
                except StopIteration:
                    self.fail(f"Watermark test output file not found: *_{anchor}.png, Info: {msg}, Directory content: {list(self.output_dir.glob('*'))}")
                
                with Image.open(out_file) as img:
                    self.assertEqual(img.mode, "RGBA", "Watermark overlay should maintain the Alpha channel")

    def test_color_adjuster_scaling(self):
        """Rule 3: Runtime Flow - Extreme parameter combination analysis"""
        # Test 2x contrast + 0x brightness (all black)
        config = {
            "contrast": 2.0,
            "brightness": 0.0,
            "sharpness": 1.0,
            "color": 1.0,
            "output_dir": str(self.output_dir),
            "template": "{filename}_color_tuned"
        }
        success, msg = process_image(str(self.rgba_path), "color_adjuster", config)
        self.assertTrue(success, f"Color adjustment test failed: {msg}")
        
        try:
            out_file = next(self.output_dir.glob("*_color_tuned.png"))
        except StopIteration:
            self.fail(f"Color adjustment output file not found: {msg}, Directory content: {list(self.output_dir.glob('*'))}")
            
        with Image.open(out_file) as img:
            pixels = list(img.convert("RGB").getdata())
            is_all_black = all(p == (0, 0, 0) for p in pixels)
            self.assertTrue(is_all_black, "Parameter adaptation error: brightness 0 should produce an all-black image")

    def test_format_converter_flattens_alpha_for_jpeg(self):
        """Images with alpha channel should be automatically flattened when exported to JPEG to avoid saving failure"""
        config = {
            "format": "JPEG",
            "quality": 90,
            "output_dir": str(self.output_dir),
            "template": "alpha_to_jpeg"
        }
        success, msg = process_image(str(self.rgba_path), "format_converter", config)
        self.assertTrue(success, msg)

        out_file = self.output_dir / "alpha_to_jpeg.jpg"
        self.assertTrue(out_file.exists())
        with Image.open(out_file) as img:
            self.assertEqual(img.mode, "RGB")

    def test_canvas_adjuster_mixed_inputs(self):
        """Rule 3: Parameter Combination - Adaptation of float (ratio) and int (absolute pixels)"""
        test_cases = [
            {"width": 150, "height": 150, "anchor": "center", "expected_size": (150, 150)}, # Absolute pixels
            {"width": 2.0, "height": 0.5, "anchor": "top-left", "expected_size": (200, 50)}, # Ratio
        ]
        
        for case in test_cases:
            with self.subTest(case=case):
                # Clear output
                for f in self.output_dir.glob("*"): f.unlink()
                
                success, msg = process_image(str(self.rgba_path), "canvas_adjuster", {**case, "output_dir": str(self.output_dir), "template": "{filename}_adjusted"})
                self.assertTrue(success, f"Canvas adjustment test failed [Case: {case}]: {msg}")
                
                try:
                    out_file = next(self.output_dir.glob("*_adjusted.png"))
                except StopIteration:
                    self.fail(f"Canvas adjustment output file not found: {msg}, Directory content: {list(self.output_dir.glob('*'))}")
                
                with Image.open(out_file) as img:
                    self.assertEqual(img.size, case["expected_size"])

    def test_large_grid_completes(self):
        """Rule 3: Full Workflow Execution - 400-block large-scale splitting stress test"""
        img = Image.new("RGB", (400, 400), color="green")
        path = self.test_dir / "large.png"
        img.save(path)
        
        config = SplitConfig(rows=20, cols=20, output_dir=str(self.output_dir))
        success, msg = process_image(str(path), "grid_splitter", config)
        self.assertTrue(success)
        files = list(self.output_dir.glob("*"))
        self.assertEqual(len(files), 400)

    def test_pixel_accuracy(self):
        """Rule 3: Key Point Analysis - Verify that processed sub-image pixels are identical to the original image"""
        img = Image.new("RGB", (100, 100))
        for x in range(100):
            for y in range(100):
                img.putpixel((x, y), (x * 2, y * 2, 128))
        test_path = self.test_dir / "gradient.png"
        img.save(test_path)
        
        config = SplitConfig(rows=2, cols=2, output_dir=str(self.output_dir))
        success, _ = process_image(str(test_path), "grid_splitter", config)
        self.assertTrue(success)
        
        tiles = sorted(self.output_dir.glob("*.png"))
        with Image.open(tiles[0]) as tile:
            self.assertEqual(tile.getpixel((0, 0)), (0, 0, 128))
            self.assertEqual(tile.getpixel((49, 49)), (98, 98, 128))

    def test_zero_pixel_avoidance(self):
        """Rule 3: Handling Extreme Cases - Tolerance when offsets lead to extremely small regions"""
        # Original image 100x100, offset (48, 48, 48, 48) -> 4x4 remaining
        # Split into 5x5 -> there will definitely be 0px cases
        config = SplitConfig(rows=5, cols=5, output_dir=str(self.output_dir), offsets=(48, 48, 48, 48))
        success, msg = process_image(str(self.rgba_path), "grid_splitter", config)
        self.assertTrue(success, f"Processing extremely small regions should not raise an error: {msg}")
        files = list(self.output_dir.glob("*"))
        self.assertGreater(len(files), 0)

if __name__ == '__main__':
    unittest.main()
