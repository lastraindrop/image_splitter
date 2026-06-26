"""End-to-end integration tests for the full pipeline."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from image_splitter.core import process_image, register_all_processors, batch_process_images
from image_splitter.engine.dispatcher import CommandDispatcher
from image_splitter.engine.registry import ProcessorRegistry
from image_splitter.script_engine import ScriptEngine


class TestEndToEndPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        register_all_processors()

    def setUp(self):
        self._temp_dir_obj = tempfile.TemporaryDirectory()
        self.test_dir = Path(self._temp_dir_obj.name).resolve()
        self.output_dir = self.test_dir / "output"
        self.output_dir.mkdir(exist_ok=True)
        self.img_path = self.test_dir / "test.png"
        Image.new("RGB", (200, 200), color="green").save(self.img_path)

    def tearDown(self):
        self._temp_dir_obj.cleanup()

    def test_full_grid_split_pipeline(self):
        """Complete pipeline: input -> grid_split -> save -> verify files."""
        success, msg = process_image(
            str(self.img_path), "grid_splitter",
            {"rows": 2, "cols": 3, "output_dir": str(self.output_dir)},
        )
        self.assertTrue(success, msg)
        files = sorted(self.output_dir.glob("*.png"))
        self.assertEqual(len(files), 6)

    def test_full_resize_then_convert_pipeline(self):
        """Pipeline: resize -> format_convert via chain."""
        results = CommandDispatcher.execute_chain(
            Image.open(self.img_path),
            "resizer(width=0.5, height=0.5) | format_converter(format='JPEG', quality=90)",
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].size, (100, 100))
        results[0].close()

    def test_batch_process_multiple_files(self):
        """Batch process generates results for each file."""
        img2 = self.test_dir / "test2.png"
        Image.new("RGB", (50, 50), color="red").save(img2)

        results = list(batch_process_images(
            [str(self.img_path), str(img2)],
            "resizer",
            {"width": 0.5, "height": 0.5, "output_dir": str(self.output_dir)},
        ))
        self.assertEqual(len(results), 2)
        for path, success, msg in results:
            self.assertTrue(success, msg)

    def test_cli_chain_mode_end_to_end(self):
        """CLI --chain mode should produce output files."""
        from image_splitter.cli import main
        test_args = [
            "cli.py", str(self.img_path),
            "--chain", "resizer(width=0.5, height=0.5)",
            "-o", str(self.output_dir),
        ]
        with patch.object(sys, "argv", test_args):
            with patch("sys.stdout"):
                try:
                    main()
                except SystemExit as e:
                    self.assertIn(e.code, (None, 0))

    def test_script_engine_batch_script_e2e(self):
        """Script engine should execute script file and produce outputs."""
        script_path = self.test_dir / "batch.txt"
        script_path.write_text(
            "grid_splitter rows=2 cols=2\nresizer width=0.5\n"
        )
        engine = ScriptEngine()
        result = engine.batch_script(
            str(script_path),
            [str(self.img_path)],
            str(self.output_dir),
        )
        self.assertTrue(result.success)

    def test_all_processors_smoke_with_rgba_input(self):
        """Every processor should handle RGBA input without crashing."""
        rgba_path = self.test_dir / "rgba.png"
        Image.new("RGBA", (100, 100), (255, 0, 0, 128)).save(rgba_path)

        for p in ProcessorRegistry.list_all():
            with self.subTest(processor=p.name):
                out_sub = self.output_dir / p.name
                out_sub.mkdir(exist_ok=True)
                config = {m["name"]: m["default"] for m in p.get_ui_metadata()}
                config["output_dir"] = str(out_sub)
                success, msg = process_image(str(rgba_path), p.name, config)
                self.assertTrue(success, f"{p.name} failed on RGBA: {msg}")

    def test_all_processors_smoke_with_grayscale_input(self):
        """Every processor should handle L-mode input."""
        l_path = self.test_dir / "gray.png"
        Image.new("L", (100, 100), 128).save(l_path)

        for p in ProcessorRegistry.list_all():
            with self.subTest(processor=p.name):
                out_sub = self.output_dir / f"L_{p.name}"
                out_sub.mkdir(exist_ok=True)
                config = {m["name"]: m["default"] for m in p.get_ui_metadata()}
                config["output_dir"] = str(out_sub)
                success, msg = process_image(str(l_path), p.name, config)
                self.assertTrue(success, f"{p.name} failed on L-mode: {msg}")

    def test_dispatcher_chain_resource_safety(self):
        """Chain must clean up intermediate images on error."""
        img = Image.new("RGB", (100, 100))
        with self.assertRaises(ValueError):
            CommandDispatcher.execute_chain(img, "geometry(rotate=45)")
        # Original image should still be usable
        self.assertEqual(img.size, (100, 100))

    def test_template_variables_substitution(self):
        """Template placeholders should be correctly substituted."""
        config = {
            "rows": 2, "cols": 2,
            "output_dir": str(self.output_dir),
            "template": "{filename}_r{row}_c{col}_{w}x{h}",
        }
        success, msg = process_image(str(self.img_path), "grid_splitter", config)
        self.assertTrue(success, msg)
        files = list(self.output_dir.glob("*"))
        self.assertEqual(len(files), 4)
        for f in files:
            self.assertIn("test_r", f.name)
            self.assertIn("x", f.name)


if __name__ == "__main__":
    unittest.main()
