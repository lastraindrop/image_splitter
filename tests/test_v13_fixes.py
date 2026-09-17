"""Regression tests for the V13 audit & fix round.

Each test locks in one confirmed bug from the 2026-09 engineering audit:

* PKG-1  — package installs correctly (import + __version__)
* KEY-1  — every default keymap action has a GUI handler (Ctrl+Shift+R
           was dead: keymap said ``toggle_macro`` but GUI only knew
           ``toggle_macro_record``)
* BORDER-1 — double border with width=1 silently cropped content via
           ``ImageOps.expand(border=-1)``
* CONSOLE-1 — console '|' chains dispatch through the async host handler
           instead of freezing the Tk main thread
* CLI-1  — --chain / --script modes expand directories and wildcards
           like the normal mode
* PRESET-1 — an explicit ``-p`` beats the processor stored in a preset
* PIPE-1 — PipelineStep.to_spec skips None values (``key=None`` used to
           become the string "None" and break coercion)
* L-3    — chain output honours a trailing format_converter (extension
           + quality) instead of hard-coded .png
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image


class TestPackaging(unittest.TestCase):
    """PKG-1: standard layout installs and exposes a version."""

    def test_version_exposed(self):
        import image_splitter
        self.assertTrue(hasattr(image_splitter, "__version__"))
        self.assertRegex(image_splitter.__version__, r"^\d+\.\d+\.\d+$")


class TestBorderDoubleDegenerateWidth(unittest.TestCase):
    """BORDER-1: double border must never crop image content."""

    def setUp(self):
        from image_splitter.processors.border import BorderProcessor
        self.proc = BorderProcessor()
        self.img = Image.new("RGB", (10, 10), (255, 0, 0))

    def test_width_1_preserves_content_and_size(self):
        result = self.proc.process(
            self.img, {"width": 1, "color": "#000000", "style": "double"}
        )[0][0]
        # 10px + 1px border per side = 12px; content must be fully intact
        # (the old code cropped 1px of content off each side).
        self.assertEqual(result.size, (12, 12))
        self.assertEqual(result.getpixel((5, 5)), (255, 0, 0))

    def test_width_2_preserves_content(self):
        result = self.proc.process(
            self.img, {"width": 2, "color": "#000000", "style": "double"}
        )[0][0]
        self.assertEqual(result.size, (14, 14))
        self.assertEqual(result.getpixel((7, 7)), (255, 0, 0))

    def test_width_3_and_above_still_composite(self):
        result = self.proc.process(
            self.img, {"width": 5, "color": "#0000ff", "style": "double"}
        )[0][0]
        # 5px per side: outer(2) + gap(1) + line(1) ... total >= requested
        self.assertEqual(result.size, (20, 20))
        # Outer ring is the border colour
        self.assertEqual(result.getpixel((0, 0)), (0, 0, 255))
        # Content survives in the middle
        self.assertEqual(result.getpixel((10, 10)), (255, 0, 0))


class TestKeymapActionCoverage(unittest.TestCase):
    """KEY-1: every default keymap action must be handled by the GUI."""

    def test_default_actions_have_gui_handlers(self):
        try:
            import customtkinter as ctk
        except ImportError:
            self.skipTest("customtkinter not available")

        import tempfile
        from unittest.mock import patch as mock_patch

        from image_splitter.gui import ImageSplitterApp
        from image_splitter.keymap import DEFAULT_KEYMAP

        # Isolate from any keymap.json in the real user home (other tests
        # may have written experimental bindings there).
        with tempfile.TemporaryDirectory() as cfg_dir:
            with mock_patch(
                "image_splitter.keymap.get_config_dir",
                return_value=Path(cfg_dir),
            ):
                root = ctk.CTk()
                root.withdraw()
                try:
                    app = ImageSplitterApp(root)
                    handlers = app._action_handlers()
                    for context, binds in DEFAULT_KEYMAP.items():
                        for seq, action in binds.items():
                            self.assertIn(
                                action, handlers,
                                f"Keymap action '{action}' ({context}: {seq}) "
                                f"has no GUI handler — this keybinding is dead"
                            )
                finally:
                    root.destroy()


class TestPipelineStepNoneFiltering(unittest.TestCase):
    """PIPE-1: None params must not leak into chain specs."""

    def test_to_spec_skips_none(self):
        try:
            from image_splitter.ui.pipeline import PipelineStep
        except ImportError:  # pragma: no cover - depends on environment
            self.skipTest("customtkinter (GUI extra) is not installed")
        step = PipelineStep("resizer", {"width": 0.5, "height": None})
        spec = step.to_spec()
        self.assertIn("width=0.5", spec)
        self.assertNotIn("height", spec)
        self.assertNotIn("None", spec)


class TestChainOutputSpec(unittest.TestCase):
    """L-3: chain output honours a trailing format_converter."""

    def test_default_is_png(self):
        from image_splitter.script_engine import chain_output_spec
        ext, kwargs = chain_output_spec("resizer(width=0.5)")
        self.assertEqual(ext, "png")
        self.assertEqual(kwargs, {})

    def test_format_converter_tail(self):
        from image_splitter.script_engine import chain_output_spec
        ext, kwargs = chain_output_spec(
            "resizer(width=0.5)|format_converter(format=JPEG,quality=90)"
        )
        self.assertEqual(ext, "jpg")
        self.assertEqual(kwargs, {"quality": 90})

    def test_converter_not_last_is_ignored(self):
        from image_splitter.script_engine import chain_output_spec
        ext, _ = chain_output_spec(
            "format_converter(format=WebP)|resizer(width=0.5)"
        )
        self.assertEqual(ext, "png")

    def test_invalid_spec_falls_back_to_png(self):
        from image_splitter.script_engine import chain_output_spec
        ext, kwargs = chain_output_spec("not a valid spec (((")
        self.assertEqual(ext, "png")
        self.assertEqual(kwargs, {})


class TestChainFormatEndToEnd(unittest.TestCase):
    """L-3 end-to-end: chain with format_converter writes the right ext."""

    def test_chain_writes_jpeg(self):
        import tempfile
        from image_splitter.script_engine import ScriptEngine
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "in.png"
            out_dir = Path(td) / "out"
            Image.new("RGB", (40, 40), "green").save(src)
            engine = ScriptEngine()
            result = engine.chain(
                [str(src)],
                "resizer(width=0.5,height=0.5)|format_converter(format=JPEG,quality=85)",
                str(out_dir),
            )
            self.assertTrue(result.success, result.message)
            files = list(out_dir.glob("*.jpg"))
            self.assertEqual(len(files), 1)
            with Image.open(files[0]) as got:
                self.assertEqual(got.size, (20, 20))


class TestConsoleChainDispatch(unittest.TestCase):
    """CONSOLE-1: '|' input must route through the async on_chain hook."""

    def setUp(self):
        try:
            import customtkinter as ctk
            self.root = ctk.CTk()
        except Exception:
            self.skipTest("Tk environment unavailable")
        self.root.withdraw()

    def tearDown(self):
        if hasattr(self, "root"):
            self.root.destroy()

    def test_chain_command_calls_on_chain_not_engine(self):
        from image_splitter.ui.console import ConsolePanel

        received = []

        class _NoChainEngine:
            def chain(self, *a, **k):  # pragma: no cover - must not run
                raise AssertionError("engine.chain ran on the main thread!")

        panel = ConsolePanel(
            self.root,
            script_engine=_NoChainEngine(),  # type: ignore[arg-type]
            on_chain=received.append,
            get_current_files=lambda: ["x.png"],
        )
        panel.input_entry.insert(0, "resizer(width=0.5)|filters(invert=True)")
        panel._on_enter()
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0], "resizer(width=0.5)|filters(invert=True)")

    def test_no_files_message(self):
        from image_splitter.ui.console import ConsolePanel

        class _NoChainEngine:
            def chain(self, *a, **k):  # pragma: no cover
                raise AssertionError("engine.chain must not be called")

        panel = ConsolePanel(
            self.root,
            script_engine=_NoChainEngine(),  # type: ignore[arg-type]
            on_chain=lambda spec: None,
            get_current_files=lambda: [],
        )
        panel.input_entry.insert(0, "a|b")
        panel._on_enter()  # must not raise


def _run_cli_capture(argv):
    """Run cli.main() with patched argv, capturing stdout.

    Returns ``(exit_code, output)`` where exit_code is None when main()
    returns normally.
    """
    import io
    from image_splitter import cli
    captured = io.StringIO()
    with patch.object(sys, "argv", argv):
        with patch("sys.stdout", captured):
            try:
                cli.main()
            except SystemExit as e:
                return e.code, captured.getvalue()
    return None, captured.getvalue()


class TestCliInputDiscoveryForChain(unittest.TestCase):
    """CLI-1: --chain/--script expand directories like normal mode."""

    def setUp(self):
        import tempfile
        from image_splitter.core import register_all_processors
        register_all_processors()
        self._temp = tempfile.TemporaryDirectory()
        self.test_dir = Path(self._temp.name).resolve()
        self.out_dir = self.test_dir / "out"
        self.img = self.test_dir / "a.png"
        Image.new("RGB", (60, 60), "blue").save(self.img)

    def tearDown(self):
        self._temp.cleanup()

    def test_chain_accepts_directory(self):
        code, out = _run_cli_capture([
            "cli.py", str(self.test_dir),
            "--chain", "resizer(width=0.5)",
            "-o", str(self.out_dir),
        ])
        self.assertIn(code, (None, 0), out)
        self.assertTrue(any(self.out_dir.glob("*_chain_*.png")))

    def test_script_accepts_directory(self):
        script = self.test_dir / "ops.txt"
        script.write_text("resizer width=0.5\n", encoding="utf-8")
        code, out = _run_cli_capture([
            "cli.py", str(self.test_dir),
            "-s", str(script),
            "-o", str(self.out_dir),
        ])
        self.assertIn(code, (None, 0), out)
        self.assertTrue(any(self.out_dir.glob("*.png")))


class TestPresetExplicitProcessorWins(unittest.TestCase):
    """PRESET-1: explicit -p must not be overridden by a preset."""

    def setUp(self):
        import tempfile
        from image_splitter.core import register_all_processors
        from image_splitter.engine.presets import save_preset
        register_all_processors()
        self._temp = tempfile.TemporaryDirectory()
        self.test_dir = Path(self._temp.name).resolve()
        self.out_dir = self.test_dir / "out"
        self.img = self.test_dir / "a.png"
        Image.new("RGB", (60, 60), "red").save(self.img)
        # Preset targets geometry; the test passes -p resizer explicitly.
        save_preset("geometry", "audit_preset_geom",
                    {"rotate": 90, "flip_h": False, "flip_v": False})

    def tearDown(self):
        from image_splitter.engine.presets import delete_preset
        delete_preset("audit_preset_geom")
        self._temp.cleanup()

    def test_explicit_p_beats_preset(self):
        code, out = _run_cli_capture([
            "cli.py", str(self.img),
            "-p", "resizer",
            "--preset", "audit_preset_geom",
            "--set", "width=0.5",
            "--set", "height=0.5",
            "-o", str(self.out_dir),
        ])
        self.assertIn(code, (None, 0), out)
        files = list(self.out_dir.glob("*.png"))
        self.assertEqual(len(files), 1)
        with Image.open(files[0]) as got:
            # resizer ran (30x30), not geometry rotate (60x60)
            self.assertEqual(got.size, (30, 30))

    def test_preset_processor_used_without_explicit_p(self):
        code, out = _run_cli_capture([
            "cli.py", str(self.img),
            "--preset", "audit_preset_geom",
            "-o", str(self.out_dir),
        ])
        self.assertIn(code, (None, 0), out)
        files = list(self.out_dir.glob("*.png"))
        self.assertEqual(len(files), 1)
        with Image.open(files[0]) as got:
            # geometry rotate 90 keeps 60x60 (square source)
            self.assertEqual(got.size, (60, 60))


if __name__ == "__main__":
    unittest.main()
