"""Tests for _execute_via_graph — unified Node Graph execution path."""

import unittest

from PIL import Image

from image_splitter.core import _execute_via_graph, register_all_processors
from image_splitter.engine.registry import ProcessorRegistry


class TestExecuteViaGraph(unittest.TestCase):
    """Verify the unified Node Graph execution helper."""

    @classmethod
    def setUpClass(cls):
        register_all_processors()

    def test_single_output_processor(self):
        """Resizer produces 1 output image with context."""
        processor = ProcessorRegistry.get("resizer")
        img = Image.new("RGB", (100, 100), "red")
        config = {"width": 0.5, "height": 0.5}

        results = _execute_via_graph(img, processor, config)

        self.assertEqual(len(results), 1)
        out_img, ctx = results[0]
        self.assertEqual(out_img.size, (50, 50))
        out_img.close()

    def test_multi_output_processor(self):
        """Grid splitter produces multiple output images with context dicts."""
        processor = ProcessorRegistry.get("grid_splitter")
        img = Image.new("RGB", (100, 100), "blue")
        config = {"rows": 2, "cols": 2}

        results = _execute_via_graph(img, processor, config)

        self.assertEqual(len(results), 4)
        for out_img, ctx in results:
            self.assertIn("row", ctx)
            self.assertIn("col", ctx)
            out_img.close()

    def test_context_preserved(self):
        """Context dicts carry per-output metadata (row, col, action, etc.)."""
        processor = ProcessorRegistry.get("grid_splitter")
        img = Image.new("RGB", (100, 100), "blue")
        config = {"rows": 2, "cols": 1}

        results = _execute_via_graph(img, processor, config)

        self.assertEqual(len(results), 2)
        # First cell: row 1, col 1
        _, ctx0 = results[0]
        self.assertIn("row", ctx0)
        self.assertIn("col", ctx0)
        # Second cell: row 2, col 1
        _, ctx1 = results[1]
        self.assertIn("row", ctx1)
        self.assertIn("col", ctx1)
        for img, _ in results:
            img.close()

    def test_format_converter_context(self):
        """Format converter provides ext and quality in context."""
        processor = ProcessorRegistry.get("format_converter")
        img = Image.new("RGB", (50, 50), "green")
        config = {"format": "JPEG", "quality": 90}

        results = _execute_via_graph(img, processor, config)

        self.assertEqual(len(results), 1)
        _, ctx = results[0]
        self.assertEqual(ctx.get("action"), "converted")
        self.assertEqual(ctx.get("quality"), 90)
        results[0][0].close()

    def test_caller_image_not_modified(self):
        """The input image is copied internally — caller's image survives."""
        processor = ProcessorRegistry.get("resizer")
        img = Image.new("RGB", (100, 100), "red")
        original_size = img.size

        results = _execute_via_graph(img, processor, {"width": 0.5, "height": 0.5})

        self.assertEqual(img.size, original_size)
        for out_img, _ in results:
            out_img.close()


if __name__ == "__main__":
    unittest.main()
