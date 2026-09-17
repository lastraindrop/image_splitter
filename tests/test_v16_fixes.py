"""V16 deployability regression tests.

Covers the "lightweight-but-complete, deployable" round:

* V16-1  Shared parallel batch runner (core.run_parallel_batch):
         sequential fallback, on_result callback, abort semantics.
* V16-2  ``{batch}`` template placeholder disambiguates same-stem files.
* V16-3  CLI discovery is case-insensitive (mixed-case extensions).
* V16-4  CLI duplicate-stem pre-flight warning.
* V16-5  Registry duplicate-name policy (raise by default; explicit
         plugin opt-in replaces).
* V16-6  BlendNode opacity clamping and cross-mode/size blending.
* V16-7  EvaluationCache invalidate/clear close held images.
* V16-8  Console suppresses "[OK] Dispatched" when the handler rejects.
"""
import contextlib
import io
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from image_splitter.cli import _discover_input_files
from image_splitter.core import (
    process_image,
    register_all_processors,
    run_parallel_batch,
)
from image_splitter.engine.evaluator import EvaluationCache
from image_splitter.engine.nodes import BlendNode
from image_splitter.engine.registry import ProcessorRegistry

from .conftest import TkTestCase


def _make_image(path: Path, color=(200, 40, 40)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (40, 40), color).save(path)
    return path


class TestV16ParallelRunner(unittest.TestCase):
    """V16-1: shared batch runner semantics."""

    @classmethod
    def setUpClass(cls):
        register_all_processors()

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name).resolve()
        self.out = self.dir / "out"
        self.paths = [
            str(_make_image(self.dir / f"img{i}.png")) for i in range(3)
        ]

    def tearDown(self):
        self._tmp.cleanup()

    def test_sequential_all_success(self):
        results = []
        ok, total, aborted = run_parallel_batch(
            self.paths, "resizer",
            {"width": 0.5, "height": 0.5, "output_dir": str(self.out)},
            jobs=1,
            on_result=lambda p, s, m: results.append((p, s)),
        )
        self.assertEqual((ok, total, aborted), (3, 3, False))
        self.assertEqual(len(results), 3)
        self.assertTrue(all(s for _, s in results))
        self.assertEqual(len(list(self.out.glob("*"))), 3)

    def test_abort_before_start(self):
        stop = threading.Event()
        stop.set()
        ok, total, aborted = run_parallel_batch(
            self.paths, "resizer",
            {"width": 0.5, "height": 0.5, "output_dir": str(self.out)},
            jobs=1, stop_event=stop,
        )
        self.assertEqual((ok, total, aborted), (0, 3, True))
        self.assertEqual(len(list(self.out.glob("*"))), 0)

    def test_empty_input(self):
        ok, total, aborted = run_parallel_batch([], "resizer", {}, jobs=1)
        self.assertEqual((ok, total, aborted), (0, 0, False))

    def test_failing_file_counts_as_failure(self):
        results = {}
        ok, total, aborted = run_parallel_batch(
            [str(self.dir / "missing.png"), self.paths[0]],
            "resizer",
            {"width": 0.5, "height": 0.5, "output_dir": str(self.out)},
            jobs=1,
            on_result=lambda p, s, m: results.__setitem__(p, s),
        )
        self.assertEqual((ok, total, aborted), (1, 2, False))
        self.assertFalse(results[str(self.dir / "missing.png")])


class TestV16BatchPlaceholder(unittest.TestCase):
    """V16-2: {batch} template variable."""

    @classmethod
    def setUpClass(cls):
        register_all_processors()

    def test_batch_placeholder_expands(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            src = _make_image(d / "same.png")
            out = d / "out"
            ok, msg = process_image(str(src), "resizer", {
                "width": 0.5, "height": 0.5,
                "output_dir": str(out), "template": "f_{batch}",
            }, batch_index=7)
            self.assertTrue(ok, msg)
            self.assertTrue((out / "f_07.png").exists())

    def test_batch_default_is_01(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            src = _make_image(d / "solo.png")
            out = d / "out"
            ok, msg = process_image(str(src), "resizer", {
                "width": 0.5, "height": 0.5,
                "output_dir": str(out), "template": "f_{batch}",
            })
            self.assertTrue(ok, msg)
            self.assertTrue((out / "f_01.png").exists())


class TestV16CliDiscoveryCaseInsensitive(unittest.TestCase):
    """V16-3: mixed-case extensions are discovered."""

    def test_mixed_case_extensions(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            _make_image(d / "photo.JPG")
            _make_image(d / "shot.Jpg")
            _make_image(d / "lower.png")
            (d / "ignore.txt").write_text("x")
            out_dir = d / "out"  # never created — no exclusion effect
            found = _discover_input_files(str(d), recursive=False,
                                          output_dir=out_dir.resolve())
            names = {f.name for f in found}
            self.assertEqual(names, {"photo.JPG", "shot.Jpg", "lower.png"})


class TestV16DuplicateStemWarning(unittest.TestCase):
    """V16-4: CLI warns when input stems collide (L-1 pre-flight)."""

    def run_cli_capture(self, args):
        from image_splitter.cli import main

        buf = io.StringIO()
        code = None
        with patch.object(sys, "argv", args):
            with contextlib.redirect_stdout(buf):
                try:
                    main()
                except SystemExit as e:
                    code = e.code
        return code, buf.getvalue()

    def test_duplicate_stem_warning_printed(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            _make_image(d / "a" / "same.png")
            _make_image(d / "b" / "same.png")
            out = d / "out"
            code, output = self.run_cli_capture([
                "cli.py", str(d), "--recursive", "-r", "1", "-c", "1",
                "-o", str(out), "-j", "1",
                "--template", "{filename}_{batch}",
            ])
            self.assertIn("duplicated stem", output)
            self.assertIn("{batch}", output)
            self.assertIn(code, (None, 0))
            # {batch} disambiguates: two distinct outputs.
            produced = sorted(p.name for p in out.glob("same_*.png"))
            self.assertEqual(produced, ["same_01.png", "same_02.png"])


class TestV16RegistryPolicy(unittest.TestCase):
    """V16-5: duplicate registration requires explicit opt-in."""

    def setUp(self):
        register_all_processors()

    def tearDown(self):
        register_all_processors()

    def _fake(self, name):
        from image_splitter.engine.base import BaseProcessor

        class _Fake(BaseProcessor):
            @property
            def name(self):
                return name

            @property
            def display_name(self):
                return name.title()

            def process(self, image, config):
                return [(image.copy(), {})]

        return _Fake()

    def test_duplicate_raises_and_keeps_original(self):
        first = self._fake("v16_dup")
        second = self._fake("v16_dup")
        ProcessorRegistry.register(first)
        with self.assertRaises(ValueError):
            ProcessorRegistry.register(second)
        self.assertIs(ProcessorRegistry.get("v16_dup"), first)

    def test_explicit_override_replaces(self):
        first = self._fake("v16_dup2")
        second = self._fake("v16_dup2")
        ProcessorRegistry.register(first)
        ProcessorRegistry.register(second, allow_override=True)
        self.assertIs(ProcessorRegistry.get("v16_dup2"), second)


class TestV16BlendNodeHardening(unittest.TestCase):
    """V16-6: opacity clamping + derived-image lifecycle."""

    @staticmethod
    def _feed(node, a, b):
        node.inputs["image_a"].value = a
        node.inputs["image_b"].value = b
        node.evaluate()
        return node.outputs["image"].value

    def test_opacity_clamped(self):
        a = Image.new("RGB", (10, 10), (0, 0, 0))
        b = Image.new("RGB", (10, 10), (255, 255, 255))
        node = BlendNode("bl")
        node.set_prop("opacity", 99)
        out = self._feed(node, a, b)
        # opacity clamped to 1.0 → pure white
        self.assertEqual(out.getpixel((0, 0)), (255, 255, 255))

    def test_bad_opacity_falls_back(self):
        a = Image.new("RGB", (10, 10), (0, 0, 0))
        b = Image.new("RGB", (10, 10), (255, 255, 255))
        node = BlendNode("bl")
        node.set_prop("opacity", "not-a-number")
        out = self._feed(node, a, b)
        # fallback 0.5 → mid gray (PIL truncates 127.5 → 127)
        self.assertIn(out.getpixel((0, 0)), ((127, 127, 127), (128, 128, 128)))

    def test_cross_mode_cross_size_blend(self):
        a = Image.new("RGB", (10, 10), (0, 0, 0))
        b = Image.new("RGBA", (20, 20), (255, 255, 255, 255))
        node = BlendNode("bl")
        out = self._feed(node, a, b)
        self.assertEqual(out.size, (10, 10))
        self.assertEqual(out.mode, "RGB")


class TestV16CacheCloseConsistency(unittest.TestCase):
    """V16-7: invalidate()/clear() close held images like eviction does."""

    def test_invalidate_closes(self):
        cache = EvaluationCache(max_entries=4)
        img = Image.new("RGB", (5, 5))
        cache.put("n", 1, img)
        cache.invalidate("n")
        with self.assertRaises(ValueError):
            img.load()

    def test_clear_closes(self):
        cache = EvaluationCache(max_entries=4)
        img = Image.new("RGB", (5, 5))
        cache.put("n", 1, img)
        cache.clear()
        with self.assertRaises(ValueError):
            img.load()


class TestV16ConsoleRejectSuppression(TkTestCase):
    """V16-8: rejected console dispatches print no "[OK] Dispatched"."""

    register_processors = True

    def test_rejected_dispatch_not_confirmed(self):
        from image_splitter.ui.console import ConsolePanel

        outputs: list[tuple[str, str]] = []
        panel = ConsolePanel(
            self.root,
            on_execute=lambda op, cfg: False,  # reject (no files loaded)
        )
        # Route output into a capture list instead of the widget.
        panel.append_output = lambda text, tag="output": outputs.append((text, tag))  # type: ignore[method-assign]
        panel.input_entry.insert(0, "resizer width=0.5")
        panel._on_enter()
        texts = "".join(t for t, _ in outputs)
        self.assertNotIn("Dispatched", texts)

    def test_accepted_dispatch_confirmed(self):
        from image_splitter.ui.console import ConsolePanel

        outputs: list[tuple[str, str]] = []
        panel = ConsolePanel(
            self.root,
            on_execute=lambda op, cfg: True,
        )
        panel.append_output = lambda text, tag="output": outputs.append((text, tag))  # type: ignore[method-assign]
        panel.input_entry.insert(0, "resizer width=0.5")
        panel._on_enter()
        texts = "".join(t for t, _ in outputs)
        self.assertIn("[OK] Dispatched: resizer", texts)


if __name__ == "__main__":
    unittest.main()
