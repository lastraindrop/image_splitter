# image_splitter/tests/test_settings.py
"""Tests for the settings persistence system."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from image_splitter import settings


class TestSettings(unittest.TestCase):
    def setUp(self):
        self._temp_dir_obj = tempfile.TemporaryDirectory()
        self.test_config_dir = Path(self._temp_dir_obj.name) / ".image_splitter"
        self.test_config_dir.mkdir(parents=True, exist_ok=True)
        self.test_settings_path = self.test_config_dir / "settings.json"

    def tearDown(self):
        self._temp_dir_obj.cleanup()

    def _patch_paths(self):
        return patch.object(settings, "get_settings_path", return_value=self.test_settings_path)

    def test_default_settings_keys(self):
        defaults = settings.DEFAULT_SETTINGS
        self.assertIn("output_dir", defaults)
        self.assertIn("default_processor", defaults)
        self.assertIn("template", defaults)
        self.assertIn("max_workers", defaults)

    def test_load_settings_returns_defaults_when_no_file(self):
        with self._patch_paths():
            result = settings.load_settings()
        self.assertEqual(result["output_dir"], "./output")
        self.assertEqual(result["default_processor"], "grid_splitter")

    def test_save_and_load_roundtrip(self):
        with self._patch_paths():
            custom = {"output_dir": "/custom/path", "max_workers": 4}
            settings.save_settings(custom)
            loaded = settings.load_settings()
        self.assertEqual(loaded["output_dir"], "/custom/path")
        self.assertEqual(loaded["max_workers"], 4)

    def test_load_settings_merges_with_defaults(self):
        with self._patch_paths():
            settings.save_settings({"max_workers": 8})
            loaded = settings.load_settings()
        self.assertEqual(loaded["max_workers"], 8)
        self.assertEqual(loaded["output_dir"], "./output")

    def test_get_setting_returns_value(self):
        with self._patch_paths():
            settings.save_settings({"template": "{filename}_{row}_{col}"})
            val = settings.get_setting("template")
        self.assertEqual(val, "{filename}_{row}_{col}")

    def test_get_setting_returns_default_for_missing(self):
        with self._patch_paths():
            val = settings.get_setting("nonexistent_key", "fallback")
        self.assertEqual(val, "fallback")

    def test_set_setting_updates_single_key(self):
        with self._patch_paths():
            settings.set_setting("max_workers", 16)
            val = settings.get_setting("max_workers")
        self.assertEqual(val, 16)

    def test_corrupt_json_returns_defaults(self):
        self.test_settings_path.write_text("{invalid json!!!")
        with self._patch_paths():
            result = settings.load_settings()
        self.assertEqual(result["output_dir"], "./output")


if __name__ == "__main__":
    unittest.main()
