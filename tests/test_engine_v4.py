"""Tests for engine v4."""

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from image_splitter.core import process_image, register_all_processors
from image_splitter.engine.registry import ProcessorRegistry
from image_splitter.models import SplitConfig

class TestEngineFramework(unittest.TestCase):
    """
    Rule 1: Always adapt to the latest plugin architecture.
    Rule 3: Verify whether the architecture runs correctly.
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
        
        # Create a complex test image (100x100) so quality parameters produce size differences
        img = Image.new("RGB", (100, 100))
        # Add some noise
        for x in range(100):
            for y in range(100):
                img.putpixel((x, y), (x % 255, y % 255, (x+y) % 255))
        self.img_path = self.test_dir / "base_test.png"
        img.save(self.img_path)

    def tearDown(self):
        self._temp_dir_obj.cleanup()

    def test_registry_integrity(self):
        """Architecture check: whether all processors follow the V4.0 standard protocol."""
        processors = ProcessorRegistry.list_all()
        self.assertGreater(len(processors), 0, "Registry should not be empty")
        
        required_attrs = ["name", "display_name", "category", "process", "draw_preview", "get_ui_metadata"]
        for p in processors:
            with self.subTest(processor=p.name):
                for attr in required_attrs:
                    self.assertTrue(hasattr(p, attr), f"Processor {p.name} missing core interface: {attr}")

    def test_processor_generic_smoke(self):
        """Parameter adaptation check: whether all processors can accept basic dict calls without crashing."""
        processors = ProcessorRegistry.list_all()
        for p in processors:
            with self.subTest(processor=p.name):
                # Construct minimum valid config
                ui_meta = p.get_ui_metadata()
                mock_config = {m["name"]: m["default"] for m in ui_meta}
                mock_config["output_dir"] = str(self.output_dir)
                
                # Run processing
                success, msg = process_image(str(self.img_path), p.name, mock_config)
                self.assertTrue(success, f"Processor {p.name} failed under default config: {msg}")
                
                # Verify if files are generated
                generated = list(self.output_dir.glob("*"))
                self.assertGreater(len(generated), 0, f"Processor {p.name} generated no files")
                
                # Clean up for next sub-test
                for f in generated: f.unlink()

    def test_path_security_regression(self):
        """Rule 3: Key points - path traversal and template safety."""
        malicious_template = "../shady_{filename}_{index}"
        config = SplitConfig(rows=1, cols=1, output_dir=str(self.output_dir), template=malicious_template)
        
        success, msg = process_image(str(self.img_path), "grid_splitter", config)
        self.assertTrue(success)
        
        # Verify if file is "forced" to stay within output_dir
        expected_name = f"shady_{self.img_path.stem}_01.png"
        evil_path = self.output_dir.parent / expected_name
        safe_path = self.output_dir / expected_name
        
        self.assertFalse(evil_path.exists(), "Security vulnerability: file successfully escaped output directory!")
        self.assertTrue(safe_path.exists(), "File should be generated in the safe directory")

    def test_save_format_parameter_adaptation(self):
        """Rule 3: Parameter combination adaptation - verify transfer of quality parameters across formats."""
        # Test WebP high compression
        config = {
            "format": "WebP",
            "quality": 10,
            "output_dir": str(self.output_dir),
            "template": "low_q"
        }
        success, _ = process_image(str(self.img_path), "format_converter", config)
        self.assertTrue(success)
        
        generated_low = self.output_dir / "low_q.webp"
        self.assertTrue(generated_low.exists())
        low_q_size = generated_low.stat().st_size
        
        # Test WebP high quality
        config["quality"] = 100
        config["template"] = "high_q"
        process_image(str(self.img_path), "format_converter", config)
        generated_high = self.output_dir / "high_q.webp"
        self.assertTrue(generated_high.exists())
        high_q_size = generated_high.stat().st_size
        
        # Quality parameter should significantly affect file size
        self.assertGreater(high_q_size, low_q_size, f"Quality parameter not effective: {high_q_size} <= {low_q_size}")

if __name__ == '__main__':
    unittest.main()
