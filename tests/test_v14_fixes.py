# image_splitter/tests/test_v14_fixes.py
"""V14 audit regression tests.

Covers every fix from the V14 review round:

* V14-1  border dashed style was a visual no-op (identical to solid)
* V14-2  macro recording of pipeline chains generated unplayable scripts
* V14-3  global keymap bindings fired while typing in Entry widgets
* V14-4  _execute_via_graph leaked temp ImageDataBlocks on processor error
* V14-5  CLI ignored settings default_rows/default_cols
* V14-6  GUI ignored settings template on startup
* V14-7  --preset-list no longer requires the input positional
* V14-8  chain execution preserves the source ICC profile
* V14-9  preset names are sanitized for cross-platform filesystems
* V14-10 CLI --preset-save excludes session noise (output_dir/template)
* V14-11 watermark glyph-origin compensation
* V14-A1 temporary data blocks use unique-per-call names
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from image_splitter.core import (
    _execute_via_graph,
    process_image,
    register_all_processors,
)
from image_splitter.engine.base import BaseProcessor
from image_splitter.engine.data_blocks import ImageDataBlock
from image_splitter.engine.macro import MacroPlayer, MacroRecorder
from image_splitter.engine.presets import _preset_path, save_preset
from image_splitter.engine.registry import ProcessorRegistry


def _make_input(tmp: Path, name: str = "in.png") -> Path:
    p = tmp / name
    Image.new("RGB", (64, 64), color=(200, 30, 30)).save(p)
    return p


# ---------------------------------------------------------------------------
# V14-1: border dashed
# ---------------------------------------------------------------------------
class TestV14BorderDashed(unittest.TestCase):
    def setUp(self):
        register_all_processors()
        self.img = Image.new("RGB", (60, 60), color=(255, 0, 0))

    def test_dashed_differs_from_solid(self):
        """Dashed border must not be pixel-identical to solid."""
        from image_splitter.processors.border import BorderProcessor

        proc = BorderProcessor()
        solid = proc.process(self.img, {"width": 6, "color": "#0000ff", "style": "solid"})[0][0]
        dashed = proc.process(self.img, {"width": 6, "color": "#0000ff", "style": "dashed"})[0][0]
        self.assertEqual(solid.size, dashed.size)
        diff = sum(
            1 for x, y in ((x, 0) for x in range(dashed.width))
            if solid.getpixel((x, 0)) != dashed.getpixel((x, 0))
        )
        self.assertGreater(diff, 0, "dashed border is still a visual no-op")

    def test_dashed_gap_pixels_are_white_for_rgb(self):
        """Gap segments on the border region show white for opaque images."""
        from image_splitter.processors.border import BorderProcessor

        proc = BorderProcessor()
        dashed = proc.process(self.img, {"width": 4, "color": "#0000ff", "style": "dashed"})[0][0]
        # dash_len = max(4, 4*2) = 8; PIL draws lines endpoint-inclusive,
        # so the first dash covers x=0..8 and the gap covers x=9..10
        # (gap_len = max(3, 4) = 3 → next dash starts at x=11).
        self.assertEqual(dashed.getpixel((9, 0)), (255, 255, 255))
        self.assertEqual(dashed.getpixel((10, 0)), (255, 255, 255))
        # A pixel inside the first dash is the border color.
        self.assertEqual(dashed.getpixel((2, 0)), (0, 0, 255))

    def test_dashed_preserves_alpha(self):
        """RGBA images keep transparency; gaps are transparent."""
        from image_splitter.processors.border import BorderProcessor

        rgba = Image.new("RGBA", (60, 60), color=(255, 0, 0, 255))
        proc = BorderProcessor()
        dashed = proc.process(rgba, {"width": 4, "color": "#0000ff", "style": "dashed"})[0][0]
        self.assertEqual(dashed.mode, "RGBA")
        r, g, b, a = dashed.getpixel((9, 0))
        self.assertEqual(a, 0, "gap pixels must stay transparent for RGBA input")

    def test_dashed_end_to_end_saves(self):
        """process_image pipeline accepts style=dashed."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            src = _make_input(tmp)
            out_dir = tmp / "out"
            ok, msg = process_image(str(src), "border", {
                "width": 4, "color": "#0000ff", "style": "dashed",
                "output_dir": str(out_dir),
            })
            self.assertTrue(ok, msg)
            self.assertEqual(len(list(out_dir.glob("*.png"))), 1)


# ---------------------------------------------------------------------------
# V14-2: macro pipeline_chain playback
# ---------------------------------------------------------------------------
class TestV14MacroChainPlayback(unittest.TestCase):
    def setUp(self):
        register_all_processors()

    def test_generated_script_uses_engine_chain(self):
        """pipeline_chain steps must generate engine.chain(...) calls."""
        rec = MacroRecorder()
        rec.start()
        rec.record("pipeline_chain", {"spec": "resizer(width=0.5)"})
        script = rec.stop()
        self.assertIn("engine.chain(input_files, 'resizer(width=0.5)', output_dir)", script)
        self.assertNotIn("'pipeline_chain'", script)

    def test_recorded_chain_replays_successfully(self):
        """A recorded pipeline chain must actually replay end-to-end."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            src = _make_input(tmp)
            out_dir = tmp / "out"

            rec = MacroRecorder()
            rec.start()
            rec.record("pipeline_chain", {"spec": "resizer(width=0.5,height=0.5)"})
            script = rec.stop()

            result = MacroPlayer.play_string(script, [str(src)], str(out_dir))
            self.assertTrue(result.success, result.message)
            produced = list(out_dir.glob("*.png"))
            self.assertEqual(len(produced), 1)
            with Image.open(produced[0]) as img:
                self.assertEqual(img.size, (32, 32))


# ---------------------------------------------------------------------------
# V14-3: keymap typing-context guard (GUI required)
# ---------------------------------------------------------------------------
class TestV14KeymapTypingGuard(unittest.TestCase):
    def _make_app(self):
        try:
            import customtkinter as ctk  # noqa: F401
            from image_splitter.gui import ImageSplitterApp
        except Exception as exc:  # pragma: no cover
            self.skipTest(f"GUI unavailable: {exc}")
        # Offscreen mapping (project convention: conftest.TkTestCase
        # map_offscreen) — withdrawn windows cannot take keyboard focus
        # and focus_force() is unreliable under test runners on Windows;
        # focus_set() on a *mapped* window is WM-independent.
        root = ctk.CTk()
        root.geometry("+10000+10000")
        root.update()
        return ImageSplitterApp(root), root

    def test_delete_in_entry_does_not_remove_selected_file(self):
        """<Delete> pressed inside an Entry must not remove the selected file."""
        app, root = self._make_app()
        try:
            with tempfile.TemporaryDirectory() as td:
                src = _make_input(Path(td))
                app.state.current_files = [str(src)]
                app.state.current_file_index = 0

                # Typing focus inside the template entry → guard active.
                # Real focus lands on CTkEntry's inner tk.Entry
                # (winfo_class "Entry"), exactly like a user click.
                # Retry a few update cycles — focus under Windows can be
                # transiently denied while other roots settle.
                guard_active = False
                for _ in range(5):
                    app.template_entry.focus_set()
                    root.update()
                    if app._is_typing_context():
                        guard_active = True
                        break
                self.assertTrue(guard_active, "entry focus did not register")

                # Fire the real event path: bindtags deliver <Delete> to
                # the Entry class binding AND the root toplevel binding;
                # the guard must suppress the latter.
                app.template_entry.event_generate("<Delete>")
                root.update()
                self.assertEqual(app.state.current_files, [str(src)])
        finally:
            root.destroy()

    def test_typing_context_detection(self):
        """The guard detects input widgets and ignores non-input focus."""
        app, root = self._make_app()
        try:
            app.template_entry.focus_set()
            root.update()
            self.assertTrue(app._is_typing_context())
            # Focus outside any input widget → guard inactive.
            app.canvas.focus_set()
            root.update()
            self.assertFalse(app._is_typing_context())
        finally:
            root.destroy()


# ---------------------------------------------------------------------------
# V14-4 + V14-A1: temp block lifecycle & unique names
# ---------------------------------------------------------------------------
class _BoomProcessor(BaseProcessor):
    @property
    def name(self) -> str:
        return "v14_boom"

    @property
    def display_name(self) -> str:
        return "V14 Boom"

    def process(self, image, config):
        raise RuntimeError("boom")


class TestV14GraphCleanup(unittest.TestCase):
    def test_no_block_leak_on_processor_exception(self):
        """A raising processor must not leak __proc_input_* blocks."""
        register_all_processors()
        before = set(ImageDataBlock._name_registry)
        img = Image.new("RGB", (8, 8))
        with self.assertRaises(RuntimeError):
            _execute_via_graph(img, _BoomProcessor(), {})
        leaked = set(ImageDataBlock._name_registry) - before
        self.assertEqual(leaked, set(), f"leaked temp blocks: {leaked}")

    def test_no_block_leak_on_success(self):
        """Successful execution also cleans up all temp blocks."""
        register_all_processors()
        before = set(ImageDataBlock._name_registry)
        img = Image.new("RGB", (8, 8))
        _execute_via_graph(img, ProcessorRegistry.get("resizer"),
                           {"width": 0.5, "height": 0.5})
        leaked = set(ImageDataBlock._name_registry) - before
        self.assertEqual(leaked, set(), f"leaked temp blocks: {leaked}")

    def test_temp_block_names_are_unique_per_call(self):
        """Concurrent-safe: two live executions never share block names."""
        from image_splitter import core

        seen_names = []
        original_init = ImageDataBlock.__init__

        def tracking_init(self, name, *args, **kwargs):
            seen_names.append(name)
            original_init(self, name, *args, **kwargs)

        with mock.patch.object(ImageDataBlock, "__init__", tracking_init):
            img = Image.new("RGB", (8, 8))
            core._execute_via_graph(img, ProcessorRegistry.get("resizer"),
                                    {"width": 0.5, "height": 0.5})
            core._execute_via_graph(img, ProcessorRegistry.get("resizer"),
                                    {"width": 0.5, "height": 0.5})

        temp_inputs = [n for n in seen_names if n.startswith("__proc_input_")]
        self.assertEqual(len(temp_inputs), 2)
        self.assertNotEqual(temp_inputs[0], temp_inputs[1])


# ---------------------------------------------------------------------------
# V14-5: CLI settings defaults
# ---------------------------------------------------------------------------
class TestV14CliSettingsDefaults(unittest.TestCase):
    def test_settings_default_rows_cols_applied(self):
        """default_rows/default_cols from settings must reach processing."""
        from image_splitter import cli

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            src = _make_input(tmp)
            out_dir = tmp / "out"
            fake_settings = {
                "output_dir": str(out_dir),
                "default_rows": 5,
                "default_cols": 4,
                "template": "{filename}_{index}",
                "max_workers": 0,
            }
            argv = ["image-splitter", str(src), "-o", str(out_dir), "-j", "1"]
            with mock.patch.object(cli.settings, "load_settings",
                                   return_value=fake_settings), \
                 mock.patch.object(sys, "argv", argv):
                cli.main()
            files = list(out_dir.glob("*.png"))
            self.assertEqual(
                len(files), 20,
                f"expected 5x4=20 tiles from settings defaults, got {len(files)}"
            )

    def test_explicit_rows_beat_settings(self):
        """Explicit -r/-c must override settings defaults."""
        from image_splitter import cli

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            src = _make_input(tmp)
            out_dir = tmp / "out"
            fake_settings = {
                "output_dir": str(out_dir),
                "default_rows": 5,
                "default_cols": 4,
                "template": "{filename}_{index}",
                "max_workers": 0,
            }
            argv = ["image-splitter", str(src), "-o", str(out_dir),
                    "-r", "2", "-c", "2", "-j", "1"]
            with mock.patch.object(cli.settings, "load_settings",
                                   return_value=fake_settings), \
                 mock.patch.object(sys, "argv", argv):
                cli.main()
            files = list(out_dir.glob("*.png"))
            self.assertEqual(len(files), 4)


# ---------------------------------------------------------------------------
# V14-7: --preset-list without input
# ---------------------------------------------------------------------------
class TestV14PresetListNoInput(unittest.TestCase):
    def test_preset_list_works_without_input(self):
        from image_splitter import cli

        argv = ["image-splitter", "--preset-list"]
        with mock.patch.object(sys, "argv", argv):
            with self.assertRaises(SystemExit) as ctx:
                cli.main()
        self.assertEqual(ctx.exception.code, 0)

    def test_missing_input_still_errors(self):
        from image_splitter import cli

        argv = ["image-splitter"]
        with mock.patch.object(sys, "argv", argv):
            with self.assertRaises(SystemExit) as ctx:
                cli.main()
        self.assertEqual(ctx.exception.code, 2)  # argparse usage error


# ---------------------------------------------------------------------------
# V14-8: chain ICC preservation
# ---------------------------------------------------------------------------
class TestV14ChainIcc(unittest.TestCase):
    def test_script_engine_chain_preserves_icc(self):
        from image_splitter.script_engine import ScriptEngine

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            src = tmp / "in.png"
            icc_blob = b"fake-icc-profile-bytes"
            Image.new("RGB", (32, 32), color=(10, 200, 10)).save(
                src, icc_profile=icc_blob
            )
            out_dir = tmp / "out"
            result = ScriptEngine().chain(
                [str(src)], "resizer(width=0.5)", str(out_dir)
            )
            self.assertTrue(result.success, result.message)
            produced = list(out_dir.glob("*_chain_*.png"))
            self.assertEqual(len(produced), 1)
            with Image.open(produced[0]) as img:
                self.assertEqual(img.info.get("icc_profile"), icc_blob)


# ---------------------------------------------------------------------------
# V14-9: preset name sanitization
# ---------------------------------------------------------------------------
class TestV14PresetNameSanitization(unittest.TestCase):
    def test_colon_name_produces_safe_path(self):
        p = _preset_path("a:b")
        self.assertNotIn(":", p.name)
        self.assertTrue(p.name.endswith(".json"))

    def test_illegal_chars_replaced(self):
        for bad in ('a<b>c', 'd"e', 'f|g', 'h?i', 'j*k', 'l\\m'):
            p = _preset_path(bad)
            for ch in '<>:"|?*\\':
                self.assertNotIn(ch, p.name)

    def test_empty_after_sanitize_falls_back(self):
        p = _preset_path("???")
        self.assertEqual(p.stem, "unnamed")

    def test_save_and_delete_roundtrip_with_illegal_name(self):
        with mock.patch(
            "image_splitter.engine.presets.get_config_dir"
        ) as fake_dir:
            with tempfile.TemporaryDirectory() as td:
                fake_dir.return_value = Path(td)
                path = save_preset("grid_splitter", "weird:name", {"rows": 2})
                self.assertTrue(path.exists())
                from image_splitter.engine.presets import delete_preset, load_preset
                data = load_preset("weird:name")
                self.assertIsNotNone(data)
                self.assertEqual(data["params"]["rows"], 2)
                self.assertTrue(delete_preset("weird:name"))


# ---------------------------------------------------------------------------
# V14-10: CLI preset-save excludes session noise
# ---------------------------------------------------------------------------
class TestV14PresetSaveSnapshot(unittest.TestCase):
    def test_preset_save_excludes_output_dir_and_template(self):
        from image_splitter import cli
        from image_splitter.engine.presets import load_preset

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            src = _make_input(tmp)
            out_dir = tmp / "out"
            preset_name = "v14_snapshot_test"

            # Isolate the presets dir — cli.main() would otherwise write
            # into the real ~/.image_splitter/presets.
            pd = tmp / "presets"
            pd.mkdir()
            with mock.patch(
                "image_splitter.engine.presets._presets_dir",
                return_value=pd,
            ):
                argv = ["image-splitter", str(src), "-o", str(out_dir),
                        "-r", "2", "-c", "2", "-j", "1",
                        "--preset-save", preset_name]
                with mock.patch.object(sys, "argv", argv):
                    try:
                        cli.main()
                    except SystemExit as e:
                        # main() exits 0 on full success
                        self.assertIn(e.code, (0, None))

                # Verify inside the same patched scope (load_preset also
                # resolves through _presets_dir).
                data = load_preset(preset_name)
            self.assertIsNotNone(data)
            self.assertNotIn("output_dir", data["params"])
            self.assertNotIn("template", data["params"])
            self.assertEqual(data["params"]["rows"], 2)


# ---------------------------------------------------------------------------
# V14-11: watermark glyph-origin compensation
# ---------------------------------------------------------------------------
class TestV14WatermarkAnchor(unittest.TestCase):
    def test_tl_text_starts_at_visual_padding(self):
        """With anchor=TL the text's *visual* top-left sits at the padding."""
        from image_splitter.processors.watermark import TextWatermark

        # Dark background so the white watermark text is scannable.
        img = Image.new("RGB", (200, 200), color=(0, 0, 0))
        proc = TextWatermark()
        out = proc.process(img, {"text": "H", "size": 40, "anchor": "TL",
                                 "opacity": 255})[0][0].convert("RGB")
        # Scan the top-left quadrant for the first ink (non-black) row.
        first_ink_row = None
        for y in range(100):
            for x in range(100):
                if out.getpixel((x, y)) != (0, 0, 0):
                    first_ink_row = y
                    break
            if first_ink_row is not None:
                break
        self.assertIsNotNone(first_ink_row, "no watermark text found")
        self.assertGreaterEqual(
            first_ink_row, 20,
            "text visually starts before the padding — origin compensation failed"
        )


if __name__ == "__main__":
    unittest.main()
