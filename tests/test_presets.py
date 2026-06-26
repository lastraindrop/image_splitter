"""Tests for parameter presets system."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from image_splitter.engine.presets import (
    save_preset,
    load_preset,
    list_presets,
    delete_preset,
    export_preset,
    import_preset,
)


class TestPresets(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self._presets_dir = Path(self.temp.name) / "presets"
        self._presets_dir.mkdir()

        patcher = patch(
            "image_splitter.engine.presets._presets_dir",
            return_value=self._presets_dir,
        )
        self.mock_presets_dir = patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.temp.cleanup)

    def test_save_and_load_roundtrip(self):
        params = {"rows": 3, "cols": 2, "offsets": [0, 0, 0, 0]}
        save_preset("grid_splitter", "Square Grid", params)
        data = load_preset("Square Grid")
        self.assertIsNotNone(data)
        self.assertEqual(data["processor"], "grid_splitter")
        self.assertEqual(data["name"], "Square Grid")
        self.assertEqual(data["params"]["rows"], 3)

    def test_load_nonexistent_returns_none(self):
        self.assertIsNone(load_preset("nonexistent"))

    def test_list_presets_sorted(self):
        save_preset("grid_splitter", "B Preset", {"rows": 2})
        save_preset("resizer", "A Preset", {"width": 0.5})
        names = list_presets()
        self.assertEqual(names, ["A Preset", "B Preset"])

    def test_list_presets_empty(self):
        self.assertEqual(list_presets(), [])

    def test_delete_preset(self):
        save_preset("resizer", "Test", {"width": 0.5})
        self.assertTrue(delete_preset("Test"))
        self.assertIsNone(load_preset("Test"))

    def test_delete_nonexistent(self):
        self.assertFalse(delete_preset("nonexistent"))

    def test_export_and_import(self):
        params = {"rows": 5, "cols": 5}
        save_preset("grid_splitter", "5x5 Grid", params)

        export_path = self._presets_dir.parent / "exported.json"
        self.assertTrue(export_preset("5x5 Grid", str(export_path)))
        self.assertTrue(export_path.exists())

        delete_preset("5x5 Grid")
        imported = import_preset(str(export_path))
        self.assertEqual(imported, "5x5 Grid")

        data = load_preset("5x5 Grid")
        self.assertIsNotNone(data)
        self.assertEqual(data["params"]["rows"], 5)

    def test_import_invalid_file(self):
        bad_path = self._presets_dir.parent / "bad.json"
        bad_path.write_text("not json", encoding="utf-8")
        self.assertIsNone(import_preset(str(bad_path)))

    def test_export_nonexistent(self):
        self.assertFalse(export_preset("nonexistent", "/tmp/out.json"))

    def test_save_sanitizes_name(self):
        save_preset("grid_splitter", "path/traversal", {"rows": 1})
        data = load_preset("path/traversal")
        self.assertIsNotNone(data)

    def test_load_corrupt_json(self):
        path = self._presets_dir / "corrupt.json"
        path.write_text("{invalid", encoding="utf-8")
        self.assertIsNone(load_preset("corrupt"))

    def test_preset_persists_across_reloads(self):
        save_preset("format_converter", "WebP HQ", {"format": "WebP", "quality": 95})
        data1 = load_preset("WebP HQ")
        data2 = load_preset("WebP HQ")
        self.assertEqual(data1["params"]["quality"], data2["params"]["quality"])


class TestCLIPresets(unittest.TestCase):
    """Test CLI integration with presets."""

    def test_preset_list_command(self):
        import sys
        from unittest.mock import patch
        from image_splitter.engine.presets import save_preset

        with tempfile.TemporaryDirectory() as td:
            pd = Path(td) / "presets"
            pd.mkdir()

            with patch("image_splitter.engine.presets._presets_dir", return_value=pd):
                save_preset("grid_splitter", "CLI_Test", {"rows": 2, "cols": 2})

                testargs = ["prog", "dummy.png", "--preset-list"]
                with patch.object(sys, "argv", testargs):
                    with patch("sys.stdout"):
                        with self.assertRaises(SystemExit) as cm:
                            from image_splitter import cli
                            cli.main()
                        self.assertEqual(cm.exception.code, 0)

    def test_preset_save_in_cli(self):
        import sys
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as td:
            pd = Path(td) / "presets"
            pd.mkdir()

            img = Path(td) / "test.png"
            from PIL import Image
            Image.new("RGB", (10, 10), "red").save(img)

            out = Path(td) / "output"

            with patch("image_splitter.engine.presets._presets_dir", return_value=pd):
                testargs = [
                    "prog", str(img), "-o", str(out),
                    "-r", "2", "-c", "2",
                    "--preset-save", "CLI_2x2",
                ]
                with patch.object(sys, "argv", testargs):
                    with patch("sys.stdout"):
                        from image_splitter import cli
                        cli.main()

                data = load_preset("CLI_2x2")
                self.assertIsNotNone(data)
                self.assertEqual(data["params"]["rows"], 2)


if __name__ == "__main__":
    unittest.main()
