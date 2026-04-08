import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from image_splitter import gui


class TestGuiSmoke(unittest.TestCase):
    def setUp(self):
        self._temp_dir_obj = tempfile.TemporaryDirectory()
        self.test_dir = Path(self._temp_dir_obj.name)
        self.output_dir = self.test_dir / "output"
        self.output_dir.mkdir(exist_ok=True)
        self.img_path = self.test_dir / "smoke.png"
        Image.new("RGB", (32, 32), color="blue").save(self.img_path)

        try:
            self.root = gui.tk.Tk()
        except gui.tk.TclError:
            self.skipTest("Tk environment unavailable")
        self.root.withdraw()
        self.app = gui.ImageSplitterApp(self.root)

    def tearDown(self):
        if hasattr(self, "root"):
            self.root.destroy()
        self._temp_dir_obj.cleanup()

    def test_app_initializes_core_widgets(self):
        self.assertTrue(hasattr(self.app, "status_label"))
        self.assertTrue(hasattr(self.app, "progress"))
        self.assertGreater(len(self.app.processor_combo["values"]), 0)

    def test_select_files_populates_list(self):
        with patch.object(gui.filedialog, "askopenfilenames", return_value=[str(self.img_path)]):
            self.app.select_files()

        self.assertEqual(len(self.app.current_files), 1)
        self.assertEqual(self.app.file_listbox.size(), 1)

    def test_clear_list_empties_state(self):
        self.app.current_files = [str(self.img_path)]
        self.app.file_listbox.insert(gui.tk.END, self.img_path.name)

        with patch.object(gui.messagebox, "askyesno", return_value=True):
            self.app.clear_list()

        self.assertEqual(self.app.file_listbox.size(), 0)
        self.assertEqual(len(self.app.current_files), 0)

    def test_run_batch_without_files_shows_warning(self):
        with patch.object(gui.messagebox, "showwarning") as warning_mock:
            self.app.run_batch()
            warning_mock.assert_called_once()

    def test_processor_switch_rebuilds_dynamic_vars(self):
        target = next(value for value in self.app.processor_combo["values"] if "Format Converter" in value)
        self.app.active_processor_name.set(target)
        self.app._on_processor_changed()

        self.assertIn("format", self.app.dynamic_vars)
        self.assertIn("quality", self.app.dynamic_vars)

    def test_run_batch_invalid_parameter_shows_error(self):
        target = next(value for value in self.app.processor_combo["values"] if "Format Converter" in value)
        self.app.active_processor_name.set(target)
        self.app._on_processor_changed()
        self.app.current_files = [str(self.img_path)]
        self.app.dynamic_vars["format"].set("INVALID")

        with patch.object(gui.filedialog, "askdirectory", return_value=str(self.output_dir)):
            with patch.object(gui.messagebox, "showerror") as error_mock:
                self.app.run_batch()
                error_mock.assert_called_once()

    def test_stop_tasks_sets_stop_event(self):
        with patch.object(gui.messagebox, "askyesno", return_value=True):
            self.app.stop_tasks()

        self.assertTrue(self.app.stop_event.is_set())
        self.assertEqual(self.app.status_label.cget("text"), "正在停止...")

    def test_finish_report_restores_button_states(self):
        self.app.btn_run.config(state=gui.tk.DISABLED)
        self.app.btn_stop.config(state=gui.tk.NORMAL)

        with patch.object(gui.messagebox, "showinfo") as info_mock:
            self.app.finish_report(1, 1, aborted=False)
            info_mock.assert_called_once()

        self.assertEqual(str(self.app.btn_run["state"]), str(gui.tk.NORMAL))
        self.assertEqual(str(self.app.btn_stop["state"]), str(gui.tk.DISABLED))


if __name__ == "__main__":
    unittest.main()
