"""Regression tests for GUI parameter widget → GuiState synchronization."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from image_splitter import gui
from .conftest import TkTestCase


class TestGuiParamSync(TkTestCase):
    map_offscreen = True

    def setUp(self):
        super().setUp()
        self._temp_dir_obj = tempfile.TemporaryDirectory()
        self.test_dir = Path(self._temp_dir_obj.name)
        self.output_dir = self.test_dir / "output"
        self.output_dir.mkdir(exist_ok=True)
        self.img_path = self.test_dir / "source.png"
        Image.new("RGB", (32, 32), color="blue").save(self.img_path)
        self.app = gui.ImageSplitterApp(self.root)

    def tearDown(self):
        super().tearDown()
        self._temp_dir_obj.cleanup()

    def _select_processor_display(self, display_fragment):
        return next(
            value for value in self.app.processor_combo.cget("values")
            if display_fragment in value
        )

    def test_entry_widget_edit_updates_state_before_batch_run(self):
        target = self._select_processor_display("Grid")
        with patch.object(self.app, "fast_update_preview"):
            self.app._on_processor_changed(target)

        rows_widget = self.app._param_widgets["rows"]
        rows_widget.delete(0, "end")
        rows_widget.insert(0, "4")
        with patch.object(self.app, "fast_update_preview") as preview_mock:
            rows_widget._entry.focus_force()
            self.root.update()
            rows_widget._entry.event_generate("<KeyRelease>")
            self.root.update()

        self.assertEqual(self.app.state.param_values["rows"], "4")
        preview_mock.assert_called()

        self.app.state.current_files = [str(self.img_path)]
        with patch.object(gui.filedialog, "askdirectory", return_value=str(self.output_dir)):
            with patch.object(gui.messagebox, "showerror"):
                with patch.object(gui.threading, "Thread") as thread_cls:
                    self.app.run_batch()

        thread_kwargs = thread_cls.call_args.kwargs
        _, processed_config, _, files = thread_kwargs["args"]
        self.assertEqual(processed_config["rows"], 4)
        self.assertEqual(files, [str(self.img_path)])
        thread_cls.return_value.start.assert_called_once()

    def test_enum_widget_edit_updates_state(self):
        target = self._select_processor_display("Format Converter")
        with patch.object(self.app, "fast_update_preview"):
            self.app._on_processor_changed(target)

        format_widget = self.app._param_widgets["format"]
        format_widget.set("JPEG")
        with patch.object(self.app, "fast_update_preview") as preview_mock:
            format_widget._command("JPEG")

        self.assertEqual(self.app.state.param_values["format"], "JPEG")
        preview_mock.assert_called_once()

    def test_bool_widget_edit_updates_state(self):
        target = self._select_processor_display("Rotate & Flip")
        with patch.object(self.app, "fast_update_preview"):
            self.app._on_processor_changed(target)

        flip_widget = self.app._param_widgets["flip_h"]
        self.assertFalse(self.app.state.param_values["flip_h"])

        flip_widget.select()
        with patch.object(self.app, "fast_update_preview") as preview_mock:
            flip_widget._command()

        self.assertEqual(self.app.state.param_values["flip_h"], 1)
        preview_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
