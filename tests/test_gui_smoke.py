"""Tests for GUI smoke — customtkinter edition.

The GUI stack (customtkinter) is an optional dependency (``[gui]`` extra,
not installed by CI's ``[dev]``).  Imports are therefore guarded: if the
GUI stack is unavailable the module collects cleanly and every test skips.
"""

import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

try:
    import customtkinter as ctk  # noqa: F401

    from image_splitter import gui
except ImportError:  # pragma: no cover - depends on environment
    gui = None  # type: ignore[assignment]

from image_splitter.engine.history import HistoryEntry


@unittest.skipIf(gui is None, "customtkinter (GUI extra) is not installed")
class TestGuiSmoke(unittest.TestCase):
    def setUp(self):
        self._temp_dir_obj = tempfile.TemporaryDirectory()
        self.test_dir = Path(self._temp_dir_obj.name)
        self.output_dir = self.test_dir / "output"
        self.output_dir.mkdir(exist_ok=True)
        self.img_path = self.test_dir / "smoke.png"
        Image.new("RGB", (32, 32), color="blue").save(self.img_path)

        try:
            root = ctk.CTk()
        except Exception:
            self.skipTest("Tk environment unavailable")
        self.root = root
        self.root.withdraw()
        self.app = gui.ImageSplitterApp(self.root)

    def tearDown(self):
        if hasattr(self, "root"):
            self.root.destroy()
        self._temp_dir_obj.cleanup()

    def test_app_initializes_core_widgets(self):
        self.assertTrue(hasattr(self.app, "status_label"))
        self.assertTrue(hasattr(self.app, "progress"))
        self.assertGreater(len(self.app.processor_combo.cget("values")), 0)

    def test_select_files_populates_list(self):
        with patch.object(gui.filedialog, "askopenfilenames", return_value=[str(self.img_path)]):
            self.app.select_files()

        self.assertEqual(len(self.app.state.current_files), 1)
        self.assertGreater(len(self.app._file_labels), 0)

    def test_clear_list_empties_state(self):
        self.app.state.current_files = [str(self.img_path)]

        with patch.object(gui.messagebox, "askyesno", return_value=True):
            self.app.clear_list()

        self.assertEqual(len(self.app._file_labels), 0)
        self.assertEqual(len(self.app.state.current_files), 0)

    def test_run_batch_without_files_shows_warning(self):
        with patch.object(gui.messagebox, "showwarning") as warning_mock:
            self.app.run_batch()
            warning_mock.assert_called_once()

    def test_processor_switch_rebuilds_dynamic_vars(self):
        target = next(value for value in self.app.processor_combo.cget("values") if "Format Converter" in value)
        self.app._on_processor_changed(target)

        self.assertIn("format", self.app.state.param_values)
        self.assertIn("quality", self.app.state.param_values)

    def test_run_batch_invalid_parameter_shows_error(self):
        target = next(value for value in self.app.processor_combo.cget("values") if "Format Converter" in value)
        self.app._on_processor_changed(target)
        self.app.state.current_files = [str(self.img_path)]
        self.app.state.param_values["format"] = "INVALID"

        with patch.object(gui.filedialog, "askdirectory", return_value=str(self.output_dir)):
            with patch.object(gui.messagebox, "showerror") as error_mock:
                self.app.run_batch()
                error_mock.assert_called_once()
        # Regression: a failed coercion used to leave _busy=True, permanently
        # locking the app.  The flag must be released on every early return.
        self.assertFalse(self.app._busy,
                         "_busy must be False after parameter-validation error")

    def test_run_batch_directory_cancel_releases_busy_flag(self):
        """Regression: if the user cancels the output-directory dialog,
        run_batch() returned without resetting _busy, leaving the app
        permanently stuck in 'operation running' state."""
        self.app.state.current_files = [str(self.img_path)]
        # Simulate the user clicking Cancel on the directory picker.
        with patch.object(gui.filedialog, "askdirectory", return_value=""):
            self.app.run_batch()
        self.assertFalse(self.app._busy,
                         "_busy must be False after directory dialog cancel")

    def test_stop_tasks_sets_stop_event(self):
        with patch.object(gui.messagebox, "askyesno", return_value=True):
            self.app.stop_tasks()

        self.assertTrue(self.app.stop_event.is_set())
        self.assertIn("Stop", self.app.status_label.cget("text"))

    def test_finish_report_restores_button_states(self):
        self.app.btn_run.configure(state="disabled")
        self.app.btn_stop.configure(state="normal")

        self.app.finish_report(1, 1, aborted=False)

        self.assertEqual(self.app.btn_run.cget("state"), "normal")
        self.assertEqual(self.app.btn_stop.cget("state"), "disabled")

    def test_undo_restores_param_values(self):
        """Undo must restore processor params + widgets, not just log."""
        # Switch to grid_splitter so param widgets exist
        target = next(
            v for v in self.app.processor_combo.cget("values")
            if "Grid" in v
        )
        self.app._on_processor_changed(target)

        # Push a history entry with different parameters
        self.app.history.push(HistoryEntry(
            timestamp=time.time(),
            operator_name="grid_splitter",
            config_snapshot={"rows": 7, "cols": 4,
                             "output_dir": str(self.output_dir),
                             "template": "{filename}_{index}"},
            input_files=[],
            description="test undo",
        ))

        # Mutate the live state (simulates user changing params)
        self.app.state.param_values["rows"] = 1
        self.app.state.param_values["cols"] = 1

        # Undo should restore the snapshot values
        self.app.undo_history()
        self.assertEqual(self.app.state.param_values["rows"], 7,
                         "undo did not restore rows to history snapshot")
        self.assertEqual(self.app.state.param_values["cols"], 4,
                         "undo did not restore cols to history snapshot")


if __name__ == "__main__":
    unittest.main()
