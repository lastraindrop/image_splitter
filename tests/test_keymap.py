# image_splitter/tests/test_keymap.py
"""Tests for the keymap/keybinding system."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from image_splitter import keymap


class TestKeymap(unittest.TestCase):
    def setUp(self):
        self._temp_dir_obj = tempfile.TemporaryDirectory()
        self.test_config_dir = Path(self._temp_dir_obj.name) / ".image_splitter"
        self.test_config_dir.mkdir(parents=True, exist_ok=True)
        self.test_keymap_path = self.test_config_dir / "keymap.json"

    def tearDown(self):
        self._temp_dir_obj.cleanup()

    def _patch_paths(self):
        return patch.object(keymap, "get_keymap_path", return_value=self.test_keymap_path)

    def test_default_keymap_has_global_context(self):
        self.assertIn("global", keymap.DEFAULT_KEYMAP)

    def test_load_keymap_returns_defaults_when_no_file(self):
        with self._patch_paths():
            result = keymap.load_keymap()
        self.assertIn("global", result)

    def test_save_and_load_roundtrip(self):
        with self._patch_paths():
            custom = {"global": {"<Ctrl-s>": "save_config"}}
            keymap.save_keymap(custom)
            loaded = keymap.load_keymap()
        self.assertEqual(loaded["global"]["<Ctrl-s>"], "save_config")

    def test_bind_adds_binding(self):
        with self._patch_paths():
            keymap.bind("global", "<Ctrl-z>", "undo")
            result = keymap.lookup("global", "<Ctrl-z>")
        self.assertEqual(result, "undo")

    def test_unbind_removes_binding(self):
        with self._patch_paths():
            keymap.bind("global", "<Ctrl-x>", "cut")
            keymap.unbind("global", "<Ctrl-x>")
            result = keymap.lookup("global", "<Ctrl-x>")
        self.assertIsNone(result)

    def test_unbind_nonexistent_is_noop(self):
        with self._patch_paths():
            keymap.unbind("global", "<Ctrl-F99>")

    def test_lookup_returns_none_for_missing(self):
        with self._patch_paths():
            result = keymap.lookup("global", "<Ctrl-Nonexistent>")
        self.assertIsNone(result)

    def test_lookup_returns_none_for_missing_context(self):
        with self._patch_paths():
            result = keymap.lookup("nonexistent_context", "<Ctrl-o>")
        self.assertIsNone(result)

    def test_reset_to_default(self):
        with self._patch_paths():
            keymap.bind("global", "<Ctrl-x>", "custom_action")
            keymap.reset_to_default()
            loaded = keymap.load_keymap()
        self.assertEqual(loaded, keymap.DEFAULT_KEYMAP)

    def test_get_context_actions(self):
        with self._patch_paths():
            actions = keymap.get_context_actions("global")
        self.assertIsInstance(actions, dict)

    def test_bind_creates_new_context(self):
        with self._patch_paths():
            keymap.bind("editor", "<Ctrl-b>", "bold")
            result = keymap.lookup("editor", "<Ctrl-b>")
        self.assertEqual(result, "bold")

    def test_multiple_binds_in_same_context(self):
        with self._patch_paths():
            keymap.bind("global", "<Ctrl-a>", "select_all")
            keymap.bind("global", "<Ctrl-c>", "copy")
            actions = keymap.get_context_actions("global")
        self.assertIn("<Ctrl-a>", actions)
        self.assertIn("<Ctrl-c>", actions)


if __name__ == "__main__":
    unittest.main()
