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


    def test_sandbox_type_is_blocked(self):
        """P0-4 regression: `type` must not be in sandbox builtins to
        prevent escape via type.__subclasses__()."""
        from image_splitter.engine.macro import _SAFE_BUILTINS
        self.assertNotIn("type", _SAFE_BUILTINS,
                         "`type` in _SAFE_BUILTINS enables sandbox escape "
                         "via type.__subclasses__() → subprocess.Popen")

    def test_sandbox_type_escape_is_prevented(self):
        """P0-4 regression: executing script that tries type.__subclasses__
        should be blocked.  Sandbox now catches NameError from run_macro()
        and returns ScriptResult(False, ...)."""
        img = self._make_test_image()
        o = Path(self.temp_dir) / "out_macro_sandbox"
        o.mkdir(exist_ok=True)

        evil_script = (
            "def run_macro(input_files, output_dir):\n"
            "    # type is not in sandbox builtins\n"
            "    classes = type.__subclasses__(type)\n"
        )

        result = MacroPlayer.play_string(evil_script, [str(img)], str(o))
        self.assertFalse(result.success,
                         f"Expected sandbox to block type escape, got: {result.message}")
        self.assertIn("type", result.message.lower(),
                      f"Expected 'type' in error message, got: {result.message}")

    def test_sandbox_sys_import_is_blocked(self):
        """SECURITY regression: `import sys` must NOT be allowed.

        Previously `sys` was in _ALLOWED_PREFIXES, which enabled a full
        sandbox escape: ``import sys`` → ``sys.modules['os']`` reaches the
        real os module (arbitrary command execution), and
        ``sys.modules['builtins'].open`` bypasses the blocked open builtin.
        This test locks the fix by asserting the import is rejected.
        """
        evil_script = (
            "import sys\n"
            "def run_macro(input_files, output_dir):\n"
            "    os_module = sys.modules['os']\n"
            "    return None\n"
        )
        img = self._make_test_image()
        o = Path(self.temp_dir) / "out_sys_escape"
        o.mkdir(exist_ok=True)

        result = MacroPlayer.play_string(evil_script, [str(img)], str(o))
        self.assertFalse(result.success,
                         f"import sys must be blocked, got: {result.message}")
        # The blocked import should be reported as a security error.
        self.assertTrue(
            "blocked" in result.message.lower() or "import" in result.message.lower(),
            f"Expected import-block message, got: {result.message}",
        )

    def test_sandbox_pathlib_import_is_blocked(self):
        """SECURITY regression: `import pathlib` must NOT be allowed.

        pathlib.Path provides read_text()/write_text() which bypass the
        blocked open builtin and give the macro direct file I/O.
        """
        evil_script = (
            "import pathlib\n"
            "def run_macro(input_files, output_dir):\n"
            "    pathlib.Path('/etc/passwd').read_text()\n"
            "    return None\n"
        )
        img = self._make_test_image()
        o = Path(self.temp_dir) / "out_pathlib_escape"
        o.mkdir(exist_ok=True)

        result = MacroPlayer.play_string(evil_script, [str(img)], str(o))
        self.assertFalse(result.success,
                         f"import pathlib must be blocked, got: {result.message}")

    def test_sandbox_main_block_does_not_run_during_playback(self):
        """Generated macro scripts contain an `if __name__ == '__main__':`
        block that calls sys.exit().  During playback __name__ must NOT be
        '__main__' — otherwise that block runs and crashes the host process.
        """
        # A script whose __main__ block would call sys.exit(1) if executed.
        script = (
            "from image_splitter.script_engine import ScriptResult\n"
            "def run_macro(input_files, output_dir):\n"
            "    return ScriptResult(True, 'ok')\n"
            "\n"
            "if __name__ == '__main__':\n"
            "    import sys\n"
            "    sys.exit(1)\n"
        )
        img = self._make_test_image()
        o = Path(self.temp_dir) / "out_main_block"
        o.mkdir(exist_ok=True)

        result = MacroPlayer.play_string(script, [str(img)], str(o))
        # If the __main__ block ran, sys.exit would have raised SystemExit
        # (uncaught) and this line would never be reached.  Reaching here
        # with success proves the block was correctly skipped.
        self.assertTrue(result.success,
                        f"__main__ block should not run during playback: {result.message}")

    def _make_test_image(self) -> Path:
        from PIL import Image
        p = Path(self.temp_dir) / "sandbox_test.png"
        Image.new("RGB", (10, 10), (255, 0, 0)).save(p)
        return p


if __name__ == "__main__":
    unittest.main()
