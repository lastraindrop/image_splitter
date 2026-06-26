"""Tests for the visual pipeline editor state model and chain output."""

import unittest
from unittest.mock import patch

from image_splitter.ui.pipeline import PipelineEditor, PipelineStep
from .conftest import TkTestCase


class TestPipelineStep(unittest.TestCase):
    def test_to_spec_quotes_values_for_dispatcher_chain(self):
        step = PipelineStep("grid_splitter", {"rows": 2, "template": "tile_{index}"})

        self.assertEqual(
            step.to_spec(),
            "grid_splitter(rows=2, template='tile_{index}')",
        )

    def test_copy_is_independent_from_original_params(self):
        step = PipelineStep("resizer", {"width": 0.5})
        copied = step.copy()

        copied.params["width"] = 0.25

        self.assertEqual(step.params["width"], 0.5)
        self.assertEqual(copied.params["width"], 0.25)


class TestPipelineEditor(TkTestCase):
    register_processors = True

    def test_add_remove_and_reorder_steps_fire_change_callback(self):
        calls = []
        editor = PipelineEditor(self.root, on_change=lambda: calls.append(1))

        editor.add_step("resizer", {"width": 0.5, "height": 0.5})
        editor.add_step("grid_splitter", {"rows": 2, "cols": 2})
        self.assertEqual(editor.step_count, 2)
        self.assertEqual([s.processor_name for s in editor.steps], ["resizer", "grid_splitter"])

        editor._move_up(1)
        self.assertEqual([s.processor_name for s in editor.steps], ["grid_splitter", "resizer"])

        editor._move_down(0)
        self.assertEqual([s.processor_name for s in editor.steps], ["resizer", "grid_splitter"])

        editor._remove_step(0)
        self.assertEqual(editor.step_count, 1)
        self.assertEqual(editor.steps[0].processor_name, "grid_splitter")
        self.assertEqual(len(calls), 5)

    def test_to_chain_spec_preserves_step_order_and_params(self):
        editor = PipelineEditor(self.root)
        editor.add_step("resizer", {"width": 0.5, "height": 0.5})
        editor.add_step("grid_splitter", {"rows": 2, "cols": 2})

        self.assertEqual(
            editor.to_chain_spec(),
            "resizer(width=0.5, height=0.5)|grid_splitter(rows=2, cols=2)",
        )

    def test_steps_property_returns_defensive_copies(self):
        editor = PipelineEditor(self.root)
        editor.add_step("resizer", {"width": 0.5})

        exposed_steps = editor.steps
        exposed_steps[0].params["width"] = 0.25

        self.assertEqual(editor.steps[0].params["width"], 0.5)

    def test_clear_all_honors_confirmation(self):
        calls = []
        editor = PipelineEditor(self.root, on_change=lambda: calls.append(1))
        editor.add_step("resizer", {"width": 0.5})

        with patch("image_splitter.ui.pipeline.messagebox.askyesno", return_value=False):
            editor._clear_all()
        self.assertEqual(editor.step_count, 1)

        with patch("image_splitter.ui.pipeline.messagebox.askyesno", return_value=True):
            editor._clear_all()
        self.assertEqual(editor.step_count, 0)
        self.assertEqual(len(calls), 2)

    def test_edit_params_apply_updates_step_params(self):
        class FakeDialog:
            destroyed = False

            def title(self, _text):
                pass

            def geometry(self, _size):
                pass

            def transient(self, _parent):
                pass

            def destroy(self):
                self.destroyed = True

        class FakeLabel:
            def __init__(self, *_args, **_kwargs):
                pass

            def grid(self, *_args, **_kwargs):
                pass

            def pack(self, *_args, **_kwargs):
                pass

        class FakeWidget:
            def __init__(self, value):
                self._value = value

            def grid(self, *_args, **_kwargs):
                pass

            def get(self):
                return self._value

        class FakeButton:
            command = None

            def __init__(self, *_args, command=None, **_kwargs):
                FakeButton.command = command

            def grid(self, *_args, **_kwargs):
                pass

            def pack(self, *_args, **_kwargs):
                pass

        calls = []
        dialog = FakeDialog()
        editor = PipelineEditor(self.root, on_change=lambda: calls.append(1))
        editor.add_step("resizer", {"width": 0.5, "height": 0.5})
        calls.clear()

        def make_widget(_parent, meta, **_kwargs):
            values = {"width": "0.25", "height": "0.75"}
            return meta["name"], FakeWidget(values[meta["name"]])

        with patch("image_splitter.ui.pipeline.ctk.CTkToplevel", return_value=dialog):
            with patch("image_splitter.ui.pipeline.ctk.CTkLabel", FakeLabel):
                with patch("image_splitter.ui.pipeline.ctk.CTkButton", FakeButton):
                    with patch("image_splitter.ui.pipeline.create_param_widget", side_effect=make_widget):
                        editor._edit_params(0)
                        FakeButton.command()

        self.assertEqual(editor.steps[0].params, {"width": "0.25", "height": "0.75"})
        self.assertTrue(dialog.destroyed)
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
