"""Tests for the macro recording and playback system."""
import tempfile
import unittest
from pathlib import Path

from image_splitter.engine.macro import MacroPlayer, MacroRecorder


class TestMacro(unittest.TestCase):
    def setUp(self):
        self.recorder = MacroRecorder()
        self.temp_dir = tempfile.mkdtemp()

    def test_record_and_generate_script(self):
        self.recorder.start()
        self.recorder.record("grid_splitter", {"rows": 3, "cols": 2})
        self.recorder.record("resizer", {"width": 0.5, "height": 0.5})
        script = self.recorder.stop()

        self.assertIn("grid_splitter", script)
        self.assertIn("resizer", script)
        self.assertIn("def run_macro", script)
        self.assertIn("ScriptEngine", script)
        self.assertFalse(self.recorder.is_recording)

    def test_empty_recording_returns_empty(self):
        self.recorder.start()
        script = self.recorder.stop()
        self.assertEqual(script, "")

    def test_record_when_not_recording_raises(self):
        with self.assertRaises(RuntimeError):
            self.recorder.record("grid_splitter", {"rows": 2})

    def test_is_recording_state(self):
        self.assertFalse(self.recorder.is_recording)
        self.recorder.start()
        self.assertTrue(self.recorder.is_recording)
        self.recorder.stop()
        self.assertFalse(self.recorder.is_recording)

    def test_cancel_clears_steps(self):
        self.recorder.start()
        self.recorder.record("grid_splitter", {"rows": 2})
        self.assertEqual(self.recorder.step_count, 1)
        self.recorder.cancel()
        self.assertFalse(self.recorder.is_recording)
        self.assertEqual(self.recorder.step_count, 0)

    def test_save_creates_file(self):
        self.recorder.start()
        self.recorder.record("resizer", {"width": 0.5, "height": 0.5})
        out_path = Path(self.temp_dir) / "macro_save_test.py"
        result = self.recorder.save(str(out_path))
        self.assertTrue(result)
        self.assertTrue(out_path.exists())
        content = out_path.read_text()
        self.assertIn("resizer", content)

    def test_save_empty_recording_returns_false(self):
        self.recorder.start()
        out_path = Path(self.temp_dir) / "empty_macro.py"
        result = self.recorder.save(str(out_path))
        self.assertFalse(result)

    def test_step_count(self):
        self.assertEqual(self.recorder.step_count, 0)
        self.recorder.start()
        self.recorder.record("op1", {"a": 1})
        self.recorder.record("op2", {"b": 2})
        self.recorder.record("op3", {"c": 3})
        self.assertEqual(self.recorder.step_count, 3)

    def test_macro_player_playback(self):
        import tempfile
        from PIL import Image
        from pathlib import Path

        d = Path(tempfile.mkdtemp())
        img = d / "t.png"
        Image.new("RGB", (20, 20), "blue").save(img)
        o = d / "out"

        self.recorder.start()
        self.recorder.record("grid_splitter", {
            "rows": 2, "cols": 2, "output_dir": str(o), "template": "t_{row}_{col}"
        })
        macro_path = d / "test_macro.py"
        self.recorder.save(str(macro_path))
        self.assertFalse(self.recorder.is_recording)

        result = MacroPlayer.play(str(macro_path), [str(img)], str(o))
        self.assertTrue(result.success, result.message)
        files = list(o.glob("*.png"))
        self.assertEqual(len(files), 4)

    def test_generated_script_is_valid_python(self):
        self.recorder.start()
        self.recorder.record("grid_splitter", {"rows": 2, "cols": 1})
        self.recorder.record("filters", {"grayscale": True})
        script = self.recorder.stop()

        compile(script, "<macro>", "exec")


if __name__ == "__main__":
    unittest.main()
