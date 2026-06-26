"""Tests for metadata-driven parameter widget creation."""

import unittest

from image_splitter.ui.param_widgets import create_param_widget
from .conftest import TkTestCase


class TestParamWidgets(TkTestCase):
    map_offscreen = True

    def test_bool_widget_uses_initial_value_and_callback(self):
        calls = []
        name, widget = create_param_widget(
            self.root,
            {"name": "enabled", "type": "bool", "default": False},
            value=True,
            on_change=lambda: calls.append(widget.get()),
        )

        self.assertEqual(name, "enabled")
        self.assertTrue(widget.get())

        widget.deselect()
        widget._command()
        self.assertEqual(calls, [0])

    def test_enum_widget_sets_option_and_fires_callback(self):
        calls = []
        name, widget = create_param_widget(
            self.root,
            {
                "name": "format",
                "type": "enum",
                "default": "PNG",
                "options": ["PNG", "JPEG", "WebP"],
            },
            on_change=lambda: calls.append(widget.get()),
        )

        self.assertEqual(name, "format")
        self.assertEqual(widget.get(), "PNG")

        widget.set("JPEG")
        widget._command("JPEG")
        self.assertEqual(calls, ["JPEG"])

    def test_entry_widget_uses_default_value_and_key_release_callback(self):
        calls = []
        name, widget = create_param_widget(
            self.root,
            {"name": "rows", "type": "int", "default": 2},
            on_change=lambda: calls.append(widget.get()),
        )

        self.assertEqual(name, "rows")
        self.assertEqual(widget.get(), "2")

        widget.pack()
        self.root.update()
        widget.delete(0, "end")
        widget.insert(0, "4")
        widget._entry.focus_force()
        self.root.update()
        widget._entry.event_generate("<KeyRelease>")
        self.root.update()
        self.assertIn("4", calls)

    def test_missing_type_and_default_create_empty_string_entry(self):
        name, widget = create_param_widget(
            self.root,
            {"name": "label"},
        )

        self.assertEqual(name, "label")
        self.assertEqual(widget.get(), "")


if __name__ == "__main__":
    unittest.main()
