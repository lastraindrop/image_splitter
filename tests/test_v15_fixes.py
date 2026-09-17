"""V15 audit regression tests.

Covers the fixes from the V15 architecture/code review round:

* V15-1  Chain fan-out: mid-chain multi-output processors (splitters)
         fan out instead of silently discarding outputs 2..n.
* V15-2  Execution-path copy reduction: a single processor invocation
         makes exactly ONE defensive image copy (was 3).
* V15-3  GUI startup builds the parameter panel and honours the
         persisted ``default_processor`` setting.
* V15-4  settings.json / keymap.json containing non-dict JSON fall back
         to defaults instead of crashing at startup.
* V15-5  smart_crop detects content on light backgrounds (border-frame
         background estimation).
* V15-6  ChainAsGraph never closes the caller's (borrowed) image and
         does not leak temp blocks on mid-chain failure.
* V15-7  import_preset surfaces OSError as a failed import (None).
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from image_splitter import keymap, settings
from image_splitter.core import _execute_via_graph, register_all_processors
from image_splitter.engine.data_blocks import ImageDataBlock
from image_splitter.engine.legacy_adapter import ChainAsGraph
from image_splitter.engine.registry import ProcessorRegistry

from .conftest import TkTestCase


class _V15BoomProcessor:
    """Minimal failing processor (duck-typed — never registered globally)."""

    def get_ui_metadata(self):
        return []

    @property
    def name(self):
        return "v15_boom"

    @property
    def display_name(self):
        return "V15 Boom"

    def process(self, image, config):
        raise RuntimeError("boom")


def _make_white_bg_image() -> Image.Image:
    """White background with a dark content square in the middle."""
    img = Image.new("RGB", (100, 100), (255, 255, 255))
    img.paste((30, 30, 30), (30, 30, 70, 70))
    return img


class TestV15ChainFanOut(unittest.TestCase):
    """V15-1: mid-chain splitters fan out."""

    @classmethod
    def setUpClass(cls):
        register_all_processors()

    def test_mid_chain_splitter_fans_out(self):
        img = Image.new("RGB", (100, 100), "red")
        results = ChainAsGraph.execute_chain(
            img, "grid_splitter(rows=2,cols=2)|resizer(width=0.5,height=0.5)"
        )
        try:
            self.assertEqual(len(results), 4)
            for out in results:
                self.assertEqual(out.size, (25, 25))
        finally:
            for out in results:
                out.close()

    def test_splitter_at_end_unchanged(self):
        img = Image.new("RGB", (100, 100), "blue")
        results = ChainAsGraph.execute_chain(
            img, "grid_splitter(rows=2,cols=2)"
        )
        try:
            self.assertEqual(len(results), 4)
        finally:
            for out in results:
                out.close()

    def test_single_output_chain_identical(self):
        img = _make_white_bg_image()
        results = ChainAsGraph.execute_chain(
            img, "resizer(width=0.5,height=0.5)|filters(grayscale=True)"
        )
        try:
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].size, (50, 50))
        finally:
            for out in results:
                out.close()

    def test_caller_image_not_closed(self):
        """The chain borrows the caller's image — it must stay usable."""
        img = _make_white_bg_image()
        ChainAsGraph.execute_chain(img, "resizer(width=0.5,height=0.5)")
        # A closed image raises ValueError on save.
        import io
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        self.assertGreater(buf.tell(), 0)

    def test_no_block_leak_on_mid_chain_failure(self):
        before = set(ImageDataBlock._name_registry)
        img = Image.new("RGB", (8, 8))
        ProcessorRegistry.register(_V15BoomProcessor())
        try:
            with self.assertRaises(RuntimeError):
                ChainAsGraph.execute_chain(
                    img, "resizer(width=0.5,height=0.5)|v15_boom()"
                )
        finally:
            ProcessorRegistry.reset()
            register_all_processors()
        leaked = set(ImageDataBlock._name_registry) - before
        self.assertEqual(leaked, set(), f"leaked temp blocks: {leaked}")


class TestV15CopyReduction(unittest.TestCase):
    """V15-2: exactly one defensive copy per processor invocation."""

    @classmethod
    def setUpClass(cls):
        register_all_processors()

    def test_single_copy_for_resizer(self):
        original_copy = Image.Image.copy
        counter = {"n": 0}

        def counting_copy(self):
            counter["n"] += 1
            return original_copy(self)

        img = Image.new("RGB", (50, 50), "red")
        with mock.patch.object(Image.Image, "copy", counting_copy):
            results = _execute_via_graph(
                img, ProcessorRegistry.get("resizer"),
                {"width": 0.5, "height": 0.5},
            )
        try:
            # 1 copy: ImageInputNode handing the image to the graph.
            self.assertEqual(counter["n"], 1)
        finally:
            for out, _ in results:
                out.close()

    def test_caller_image_survives(self):
        img = Image.new("RGB", (40, 40), "green")
        results = _execute_via_graph(
            img, ProcessorRegistry.get("resizer"),
            {"width": 0.5, "height": 0.5},
        )
        self.assertEqual(img.size, (40, 40))
        import io
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        self.assertGreater(buf.tell(), 0)
        for out, _ in results:
            out.close()


class TestV15GuiStartup(TkTestCase):
    """V15-3: GUI startup builds the parameter panel."""

    register_processors = True

    def test_param_panel_built_at_startup(self):
        from image_splitter.gui import ImageSplitterApp

        app = ImageSplitterApp(self.root)
        self.root.update()
        # NOTE: no app.on_close() — it persists settings to the user's
        # real config dir; teardown destroys the window instead.
        frames = app.props_frame.winfo_children()
        self.assertGreater(
            len(frames), 0,
            "Parameters panel must be populated at startup"
        )
        # State and combo agree.
        self.assertTrue(app.state.active_processor)
        self.assertEqual(
            app.processor_combo.get(), app.state.active_processor
        )
        # Param defaults registered in state.
        self.assertTrue(app.state.param_values)

    def test_startup_honours_default_processor(self):
        from image_splitter.gui import ImageSplitterApp

        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(
                settings, "load_settings",
                return_value={"default_processor": "grid_splitter"},
            ):
                app = ImageSplitterApp(self.root)
                self.root.update()
                proc = ProcessorRegistry.get("grid_splitter")
                self.assertEqual(
                    app.state.active_processor, proc.display_name
                )


class TestV15ConfigRobustness(unittest.TestCase):
    """V15-4: non-dict JSON config files fall back to defaults."""

    def test_settings_non_dict_json(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "settings.json"
            path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
            with mock.patch.object(settings, "get_settings_path", return_value=path):
                loaded = settings.load_settings()
            self.assertIsInstance(loaded, dict)
            self.assertIn("output_dir", loaded)

    def test_keymap_non_dict_json(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "keymap.json"
            path.write_text('"just-a-string"', encoding="utf-8")
            with mock.patch.object(keymap, "get_keymap_path", return_value=path):
                loaded = keymap.load_keymap()
            self.assertIn("global", loaded)
            self.assertIn("<Control-o>", loaded["global"])


class TestV15SmartCropLightBackground(unittest.TestCase):
    """V15-5: smart_crop works on white backgrounds."""

    @classmethod
    def setUpClass(cls):
        register_all_processors()

    def test_crops_dark_content_on_white_bg(self):
        proc = ProcessorRegistry.get("smart_crop")
        img = _make_white_bg_image()
        results = proc.process(img, {"threshold": 30, "margin": 5})
        self.assertEqual(len(results), 1)
        out, ctx = results[0]
        try:
            self.assertTrue(ctx.get("cropped"))
            # Content box is (30,30)-(70,70) = 40px; +5 margin each side → 50.
            self.assertEqual(out.size, (50, 50))
        finally:
            out.close()

    def test_uniform_image_not_cropped(self):
        proc = ProcessorRegistry.get("smart_crop")
        img = Image.new("RGB", (60, 60), (200, 200, 200))
        results = proc.process(img, {"threshold": 30, "margin": 5})
        out, ctx = results[0]
        try:
            self.assertFalse(ctx.get("cropped"))
        finally:
            out.close()

    def test_dark_bg_still_works(self):
        """Pre-V15 behaviour (dark background) must keep working."""
        proc = ProcessorRegistry.get("smart_crop")
        img = Image.new("RGB", (100, 100), (0, 0, 0))
        img.paste((220, 220, 220), (40, 40, 60, 60))
        results = proc.process(img, {"threshold": 30, "margin": 2})
        out, ctx = results[0]
        try:
            self.assertTrue(ctx.get("cropped"))
            self.assertEqual(out.size, (24, 24))
        finally:
            out.close()


class TestV15ImportPresetOSError(unittest.TestCase):
    """V15-7: import_preset tolerates an unwritable presets directory."""

    def test_returns_none_on_oserror(self):
        from image_splitter.engine import presets

        with mock.patch.object(
            presets, "save_preset", side_effect=OSError("disk full")
        ):
            result = presets.import_preset("nonexistent.json")
        # Missing file short-circuits to None before save_preset is hit.
        self.assertIsNone(result)

    def test_import_preset_with_bad_save(self):
        from image_splitter.engine import presets

        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "preset.json"
            src.write_text(
                json.dumps({
                    "name": "p1", "processor": "resizer",
                    "params": {"width": 0.5},
                }),
                encoding="utf-8",
            )
            with mock.patch.object(
                presets, "save_preset", side_effect=OSError("disk full")
            ):
                result = presets.import_preset(str(src))
            self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
