"""Tests for GUI workflows — customtkinter edition."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    import customtkinter as ctk
except ImportError:
    ctk = None  # type: ignore[assignment]

from PIL import Image

try:
    from image_splitter import gui
except ImportError:
    gui = None  # type: ignore[assignment]


@unittest.skipIf(ctk is None, "customtkinter is not available")
class TestGuiWorkflows(unittest.TestCase):
    def setUp(self):
        self._temp_dir_obj = tempfile.TemporaryDirectory()
        self.test_dir = Path(self._temp_dir_obj.name)
        self.output_dir = self.test_dir / "output"
        self.output_dir.mkdir(exist_ok=True)
        self.img_path = self.test_dir / "test_gui_image.png"
        Image.new("RGB", (100, 100), color="blue").save(self.img_path)

        try:
            self.root = ctk.CTk()
        except Exception:
            self.skipTest("Tk environment unavailable (e.g. headless CI)")
        self.root.withdraw()
        self.app = gui.ImageSplitterApp(self.root)

    def tearDown(self):
        if hasattr(self, "root"):
            self.root.destroy()
        self._temp_dir_obj.cleanup()

    def test_full_workflow_config_coercion_and_run(self):
        with patch.object(gui.filedialog, "askopenfilenames", return_value=[str(self.img_path)]):
            self.app.select_files()

        self.assertEqual(len(self.app.state.current_files), 1)
        self.assertEqual(self.app.current_orig_size, (100, 100))

        target_processor_name = "Format Converter"
        self.assertIn(target_processor_name, self.app.processor_combo.cget("values"))

        self.app._on_processor_changed(target_processor_name)

        # Verify that the tooltip has been updated
        self.assertIn("Export", self.app.state.tooltip_text)

        # 3. Simulate modifying parameters
        self.assertIn("format", self.app.state.param_values)
        self.assertIn("quality", self.app.state.param_values)
        self.app.state.param_values["format"] = "JPEG"
        self.app.state.param_values["quality"] = "95"  # String type input

        # 4. Simulate running and intercept threading.Thread
        with patch.object(gui.filedialog, "askdirectory", return_value=str(self.output_dir)):
            with patch('threading.Thread') as mock_thread:
                self.app.run_batch()

                mock_thread.assert_called_once()
                args, kwargs = mock_thread.call_args

                # target=self.work_thread, args=(p_name, config, output_dir, files)
                thread_args = kwargs.get('args', args[1] if len(args) > 1 else None)
                self.assertIsNotNone(thread_args)

                p_name, processed_config, out_dir, files = thread_args
                self.assertEqual(p_name, "format_converter")
                self.assertEqual(out_dir, str(self.output_dir))

                # Verify if coercion is effective
                self.assertEqual(processed_config["format"], "JPEG")
                self.assertEqual(processed_config["quality"], 95)  # Should be int
                self.assertIsInstance(processed_config["quality"], int)


if __name__ == '__main__':
    unittest.main()
