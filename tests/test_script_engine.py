# image_splitter/tests/test_script_engine.py
"""Tests for the script engine and chain processing."""
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from image_splitter.script_engine import ScriptEngine, ScriptResult
from image_splitter.core import register_all_processors


class TestScriptEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        register_all_processors()

    def setUp(self):
        self._temp_dir_obj = tempfile.TemporaryDirectory()
        self.test_dir = Path(self._temp_dir_obj.name).resolve()
        self.output_dir = self.test_dir / "output"
        self.output_dir.mkdir(exist_ok=True)
        self.img_path = self.test_dir / "test.png"
        Image.new("RGB", (100, 100), color="blue").save(self.img_path)
        self.engine = ScriptEngine()

    def tearDown(self):
        self._temp_dir_obj.cleanup()

    def test_process_single_file(self):
        result = self.engine.process(
            [str(self.img_path)],
            "grid_splitter",
            {"rows": 2, "cols": 2, "output_dir": str(self.output_dir)},
        )
        self.assertTrue(result.success)
        self.assertIn("Processed 1/1", result.message)

    def test_process_unknown_operator(self):
        result = self.engine.process(
            [str(self.img_path)],
            "nonexistent_operator",
            {"output_dir": str(self.output_dir)},
        )
        self.assertFalse(result.success)
        self.assertIn("Unknown operator", result.message)

    def test_chain_saves_output_files(self):
        result = self.engine.chain(
            [str(self.img_path)],
            "resizer(width=0.5, height=0.5) | grid_splitter(rows=2, cols=2)",
            str(self.output_dir),
        )
        self.assertTrue(result.success)
        self.assertGreater(len(result.output_files), 0)
        for f in result.output_files:
            self.assertTrue(f.exists())

    def test_chain_resizes_then_splits(self):
        result = self.engine.chain(
            [str(self.img_path)],
            "resizer(width=0.5, height=0.5) | grid_splitter(rows=2, cols=2)",
            str(self.output_dir),
        )
        self.assertTrue(result.success)
        self.assertEqual(len(result.output_files), 4)
        for f in result.output_files:
            with Image.open(f) as img:
                self.assertEqual(img.size, (25, 25))

    def test_chain_resource_cleanup(self):
        """Chain must not leak file handles - verify images can be opened after chain."""
        result = self.engine.chain(
            [str(self.img_path)],
            "resizer(width=0.5, height=0.5)",
            str(self.output_dir),
        )
        self.assertTrue(result.success)
        for f in result.output_files:
            with Image.open(f) as img:
                self.assertEqual(img.size, (50, 50))

    def test_batch_script_file_not_found(self):
        result = self.engine.batch_script(
            "/nonexistent/script.txt",
            [str(self.img_path)],
            str(self.output_dir),
        )
        self.assertFalse(result.success)
        self.assertIn("not found", result.message)

    def test_batch_script_executes_lines(self):
        script_path = self.test_dir / "script.txt"
        script_path.write_text("# Comment\ngrid_splitter rows=1 cols=1\n")
        result = self.engine.batch_script(
            str(script_path),
            [str(self.img_path)],
            str(self.output_dir),
        )
        self.assertTrue(result.success)

    def test_execute_script_multiline(self):
        script = "grid_splitter rows=1 cols=1\nresizer width=0.5"
        result = self.engine.execute_script(
            script,
            [str(self.img_path)],
            str(self.output_dir),
        )
        self.assertTrue(result.success)

    def test_execute_script_empty_lines(self):
        script = "\n# just a comment\n\n"
        result = self.engine.execute_script(
            script,
            [str(self.img_path)],
            str(self.output_dir),
        )
        self.assertFalse(result.success)

    def test_get_available_operators(self):
        ops = self.engine.get_available_operators()
        self.assertIn("grid_splitter", ops)
        self.assertIn("resizer", ops)
        self.assertIn("text_watermark", ops)
        self.assertGreaterEqual(len(ops), 10)

    def test_script_result_dataclass(self):
        result = ScriptResult(True, "OK", [Path("/tmp/a.png")])
        self.assertTrue(result.success)
        self.assertEqual(result.message, "OK")
        self.assertEqual(len(result.output_files), 1)


if __name__ == "__main__":
    unittest.main()
