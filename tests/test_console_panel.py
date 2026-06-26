"""Tests for the embedded GUI command console."""

import unittest

from image_splitter.ui.console import ConsolePanel
from .conftest import TkTestCase


class FakeEngine:
    def __init__(self):
        self.calls = []

    def chain(self, files, spec):
        self.calls.append((list(files), spec))

        class Result:
            message = "chain complete"

        return Result()

    def get_available_operators(self):
        return ["grid_splitter", "resizer"]


class TestConsolePanel(TkTestCase):
    register_processors = True

    def _text(self, panel):
        return panel.output_text.get("1.0", "end")

    def test_operator_command_dispatches_coerced_config_and_history(self):
        calls = []
        panel = ConsolePanel(
            self.root,
            on_execute=lambda op, cfg: calls.append((op, cfg)),
        )

        panel.input_entry.insert(0, "grid_splitter rows=2 enabled=true scale=0.5")
        panel._on_enter()

        self.assertEqual(
            calls,
            [("grid_splitter", {"rows": 2, "enabled": True, "scale": 0.5})],
        )
        self.assertEqual(panel._history, ["grid_splitter rows=2 enabled=true scale=0.5"])
        self.assertIn("[OK] Dispatched: grid_splitter", self._text(panel))

        panel._history_up()
        self.assertEqual(panel.input_entry.get(), panel._history[0])
        panel._history_down()
        self.assertEqual(panel.input_entry.get(), "")

    def test_operator_command_coerces_false_and_no_values(self):
        calls = []
        panel = ConsolePanel(
            self.root,
            on_execute=lambda op, cfg: calls.append((op, cfg)),
        )

        panel.input_entry.insert(0, "grid_splitter enabled=false visible=no")
        panel._on_enter()

        self.assertEqual(
            calls,
            [("grid_splitter", {"enabled": False, "visible": False})],
        )

    def test_chain_command_uses_current_files_and_engine(self):
        engine = FakeEngine()
        panel = ConsolePanel(
            self.root,
            script_engine=engine,
            get_current_files=lambda: ["input.png"],
        )

        spec = "resizer(width=0.5)|grid_splitter(rows=2,cols=2)"
        panel.input_entry.insert(0, spec)
        panel._on_enter()

        self.assertEqual(engine.calls, [(["input.png"], spec)])
        self.assertIn("chain complete", self._text(panel))

    def test_warn_tag_is_configured_and_tab_completion_returns_break(self):
        panel = ConsolePanel(self.root)
        tag_names = panel.output_text._textbox.tag_names()

        self.assertIn("warn", tag_names)

        panel.input_entry.insert(0, "grid_spl")
        result = panel._tab_complete()
        self.assertEqual(result, "break")
        self.assertEqual(panel.input_entry.get(), "grid_splitter ")


if __name__ == "__main__":
    unittest.main()
