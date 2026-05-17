"""Tests for the user plugin system and auto-discovery."""
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from image_splitter.core import register_all_processors
from image_splitter.engine.registry import ProcessorRegistry


class TestPluginSystem(unittest.TestCase):
    def setUp(self):
        register_all_processors()

    def test_plugins_package_is_importable(self):
        from image_splitter import plugins
        self.assertIsNotNone(plugins)

    def test_example_plugin_is_registered(self):
        names = [p.name for p in ProcessorRegistry.list_all()]
        self.assertIn("invert_color", names,
                      "invert_color plugin should be auto-discovered")

    def test_example_plugin_has_metadata(self):
        proc = ProcessorRegistry.get("invert_color")
        self.assertEqual(proc.name, "invert_color")
        self.assertEqual(proc.display_name, "Invert Colors (Plugin)")
        self.assertEqual(proc.category, "Filter")
        self.assertTrue(len(proc.tool_tip) > 0)
        meta = proc.get_ui_metadata()
        self.assertEqual(len(meta), 1)
        self.assertEqual(meta[0]["name"], "invert_alpha")
        self.assertEqual(meta[0]["type"], "bool")

    def test_example_plugin_inverts_colors(self):
        proc = ProcessorRegistry.get("invert_color")
        img = Image.new("RGB", (10, 10), (255, 255, 255))
        result = proc.process(img, {})
        self.assertEqual(len(result), 1)
        out_img, ctx = result[0]
        self.assertEqual(ctx["action"], "inverted")
        pixel = out_img.getpixel((0, 0))
        self.assertEqual(pixel, (0, 0, 0))

    def test_total_processor_count_includes_plugin(self):
        names = [p.name for p in ProcessorRegistry.list_all()]
        self.assertEqual(len(names), 11,
                         f"Expected 11 processors (10 built-in + 1 plugin), got {len(names)}")

    def test_plugin_smoke_with_process_image(self):
        from image_splitter.core import process_image

        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            img_path = d / "test.png"
            Image.new("RGB", (20, 20), (255, 255, 255)).save(img_path)
            o = d / "out"

            ok, msg = process_image(
                str(img_path), "invert_color",
                {"output_dir": str(o)},
            )
            self.assertTrue(ok, msg)
            files = list(o.glob("*.png"))
            self.assertEqual(len(files), 1)
            with Image.open(files[0]) as result:
                self.assertEqual(result.getpixel((0, 0)), (0, 0, 0))


class TestHistoryIntegration(unittest.TestCase):
    def test_push_and_undo_integration(self):
        from image_splitter.engine.history import HistoryEntry, HistoryManager
        import time

        mgr = HistoryManager(max_depth=5)
        e1 = HistoryEntry(
            timestamp=time.time(),
            operator_name="grid_splitter",
            config_snapshot={"rows": 2, "cols": 2},
            input_files=["a.png"],
            description="Split: 4 tiles",
        )
        mgr.push(e1)
        self.assertTrue(mgr.can_undo())
        undone = mgr.undo()
        self.assertEqual(undone.operator_name, "grid_splitter")
        redone = mgr.redo()
        self.assertEqual(redone.operator_name, "grid_splitter")

    def test_export_log_writes_valid_json(self):
        import json
        import tempfile
        import time
        from image_splitter.engine.history import HistoryEntry, HistoryManager

        mgr = HistoryManager(max_depth=10)
        mgr.push(HistoryEntry(
            timestamp=time.time(),
            operator_name="resizer",
            config_snapshot={"width": 0.5},
            input_files=["img.png"],
            description="Resize 50%",
        ))
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            mgr.export_log(path)
            with open(path, "r") as f:
                data = json.load(f)
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["operator_name"], "resizer")
        finally:
            Path(path).unlink(missing_ok=True)


class TestMacroIntegration(unittest.TestCase):
    def test_record_then_replay(self):
        import tempfile
        from pathlib import Path
        from PIL import Image

        from image_splitter.engine.macro import MacroRecorder, MacroPlayer

        d = Path(tempfile.mkdtemp())
        img = d / "src.png"
        Image.new("RGB", (30, 30), "red").save(img)

        recorder = MacroRecorder()
        recorder.start()
        recorder.record("grid_splitter", {
            "rows": 2, "cols": 2,
            "output_dir": str(d / "macro_out"),
            "template": "t_{row}_{col}",
        })
        macro_path = d / "recording.py"
        recorder.save(str(macro_path))

        result = MacroPlayer.play(str(macro_path), [str(img)], str(d / "macro_out"))
        self.assertTrue(result.success, result.message)
        outputs = list((d / "macro_out").glob("*.png"))
        self.assertEqual(len(outputs), 4)


if __name__ == "__main__":
    unittest.main()
