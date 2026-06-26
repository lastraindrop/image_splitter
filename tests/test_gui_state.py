"""Tests for GuiState — framework-agnostic ViewModel."""

import unittest

from image_splitter.ui._state import GuiState


class TestGuiState(unittest.TestCase):
    """Verify GuiState behaves correctly as a plain-Python ViewModel."""

    def test_default_values(self):
        s = GuiState()
        self.assertEqual(s.active_processor, "")
        self.assertEqual(s.output_template, "{filename}_{index}")
        self.assertEqual(s.param_values, {})
        self.assertEqual(s.current_files, [])
        self.assertEqual(s.progress, 0.0)
        self.assertFalse(s.pipeline_visible)
        self.assertFalse(s.console_visible)
        self.assertFalse(s.macro_recording)

    def test_get_param_with_default(self):
        s = GuiState()
        self.assertIsNone(s.get_param("nonexistent"))
        self.assertEqual(s.get_param("nonexistent", 42), 42)

    def test_set_param_triggers_callback(self):
        calls = []
        s = GuiState()
        s.on_state_changed = lambda: calls.append(1)
        s.set_param("key", "value")
        self.assertEqual(len(calls), 1)
        self.assertEqual(s.param_values["key"], "value")

    def test_set_params_bulk_single_callback(self):
        calls = []
        s = GuiState()
        s.on_state_changed = lambda: calls.append(1)
        s.set_params_bulk({"a": 1, "b": 2, "c": 3})
        self.assertEqual(len(calls), 1)
        self.assertEqual(s.param_values, {"a": 1, "b": 2, "c": 3})

    def test_set_processor_clears_params(self):
        s = GuiState()
        s.param_values = {"old": "data"}
        s.set_processor("New Processor", "Tooltip text")
        self.assertEqual(s.active_processor, "New Processor")
        self.assertEqual(s.tooltip_text, "Tooltip text")
        self.assertEqual(s.param_values, {})

    def test_select_file_bounds(self):
        s = GuiState()
        s.current_files = ["a.jpg", "b.jpg", "c.jpg"]
        s.select_file(1)
        self.assertEqual(s.current_file_index, 1)
        s.select_file(999)
        self.assertEqual(s.current_file_index, 2)

    def test_clear_files_resets_preview(self):
        s = GuiState()
        s.current_files = ["a.jpg", "b.jpg"]
        s.current_file_index = 1
        s.orig_size = (100, 100)
        s.preview_ratio = 0.5
        s.clear_files()
        self.assertEqual(s.current_files, [])
        self.assertEqual(s.current_file_index, 0)
        self.assertEqual(s.orig_size, (0, 0))
        self.assertEqual(s.preview_ratio, 1.0)

    def test_set_progress_bounds(self):
        s = GuiState()
        s.set_progress(0.5, "Half done")
        self.assertEqual(s.progress, 0.5)
        self.assertEqual(s.status_text, "Half done")
        # Clamped
        s.set_progress(2.0)
        self.assertEqual(s.progress, 1.0)
        s.set_progress(-1.0)
        self.assertEqual(s.progress, 0.0)

    def test_toggle_pipeline(self):
        s = GuiState()
        self.assertFalse(s.pipeline_visible)
        s.toggle_pipeline()
        self.assertTrue(s.pipeline_visible)
        s.toggle_pipeline()
        self.assertFalse(s.pipeline_visible)

    def test_toggle_console(self):
        s = GuiState()
        self.assertFalse(s.console_visible)
        s.toggle_console()
        self.assertTrue(s.console_visible)

    def test_no_callback_no_crash(self):
        s = GuiState()
        s.on_state_changed = None
        s.set_param("x", 1)  # should not raise
        s.set_processor("test")
        s.set_progress(0.5)
        s.toggle_pipeline()


if __name__ == "__main__":
    unittest.main()
