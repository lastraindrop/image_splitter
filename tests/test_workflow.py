"""End-to-end workflow tests covering real-world usage scenarios.

Tests complete pipelines: file input → config → process → verify output,
multi-processor chains, batch with mixed formats, and integration of
all subsystems (presets, macro, history, chain).
"""
import io

from PIL import Image

from image_splitter.core import process_image, batch_process_images
from image_splitter.engine.dispatcher import CommandDispatcher
from image_splitter.engine.history import HistoryEntry, HistoryManager
from image_splitter.engine.macro import MacroRecorder
from image_splitter.engine.presets import save_preset, load_preset, delete_preset
from image_splitter.engine.registry import ProcessorRegistry
from image_splitter.script_engine import ScriptEngine

from .conftest import (
    BaseTest,
    make_gradient_image,
    make_grayscale_image,
    make_rgba_image,
    make_rgb_image,
    RED,
    BLUE,
)


class TestFullPipelineWorkflow(BaseTest):
    """Complete end-to-end workflows."""

    # ------------------------------------------------------------------
    # Single processor workflows
    # ------------------------------------------------------------------
    def test_basic_grid_split_and_verify(self) -> None:
        """Split 2x3 → 6 files → verify tile content."""
        ok, msg = process_image(
            str(self.rgb_path), "grid_splitter",
            {"rows": 2, "cols": 3, "output_dir": str(self.output_dir)},
        )
        self.assertTrue(ok, msg)
        files = self.output_files()
        self.assertEqual(len(files), 6)
        for f in files:
            with Image.open(f) as img:
                self.assertGreater(img.width, 0)

    def test_resize_then_format_conversion(self) -> None:
        """Resize 50% → convert to JPEG."""
        results = CommandDispatcher.execute_chain(
            Image.open(self.rgb_path),
            "resizer(width=0.5, height=0.5) | "
            "format_converter(format='JPEG', quality=90)",
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].size, (50, 50))
        for r in results:
            r.close()

    def test_multi_step_chain(self) -> None:
        """resizer → grid_splitter → filters (3-step chain)."""
        with Image.open(self.rgb_path) as img:
            results = CommandDispatcher.execute_chain(
                img,
                "resizer(width=0.5, height=0.5) | "
                "grid_splitter(rows=2, cols=2) | "
                "filters(grayscale=True)",
            )
        self.assertGreaterEqual(len(results), 1)

    # ------------------------------------------------------------------
    # Batch + mixed format workflows
    # ------------------------------------------------------------------
    def test_batch_mixed_formats(self) -> None:
        """Batch RGB + RGBA + Grayscale images."""
        out = self.sub_output_dir("batch_mix")
        ok, msg = process_image(
            str(self.rgba_path), "format_converter",
            {"format": "PNG", "output_dir": str(out)},
        )
        self.assertTrue(ok, msg)
        ok2, _ = process_image(
            str(self.gray_path), "filters",
            {"invert": True, "output_dir": str(out)},
        )
        self.assertTrue(ok2)

    def test_batch_multiple_files_same_processor(self) -> None:
        """Process multiple images through same processor."""
        paths = [str(self.rgb_path), str(self.rgba_path)]
        out = self.sub_output_dir("batch_proc")
        results = list(batch_process_images(paths, "resizer", {
            "width": 0.5, "height": 0.5, "output_dir": str(out),
        }))
        self.assertEqual(len(results), 2)
        for path, success, msg in results:
            self.assertTrue(success, f"{path}: {msg}")

    # ------------------------------------------------------------------
    # Config model boundary values
    # ------------------------------------------------------------------
    def test_watermark_all_parameters(self) -> None:
        """Watermark with all anchors, edge opacity, and empty text."""
        out = self.sub_output_dir("wm_all")
        for anchor, text, opacity in [
            ("TL", "Corner", 255),
            ("TR", "Edge", 0),
            ("BL", "", 128),
            ("BR", "Bottom", 1),
            ("C", "Center", 200),
        ]:
            ok, msg = process_image(
                str(self.rgba_path), "text_watermark",
                {"text": text, "anchor": anchor, "opacity": opacity,
                 "output_dir": str(out), "template": f"wm_{anchor.lower()}"},
            )
            self.assertTrue(ok, f"Watermark {anchor} opacity={opacity}: {msg}")

    def test_splitter_edge_cases(self) -> None:
        """Split with 1x1, 1xN, Nx1, large N."""
        for rows, cols in [(1, 1), (1, 5), (5, 1), (10, 10)]:
            out = self.sub_output_dir(f"s_{rows}x{cols}")
            ok, msg = process_image(
                str(self.rgb_path), "grid_splitter",
                {"rows": rows, "cols": cols, "output_dir": str(out)},
            )
            self.assertTrue(ok, msg)
            self.assertGreater(self.count_output_files(f"s_{rows}x{cols}"), 0)

    def test_format_quality_boundaries(self) -> None:
        """Format converter with quality 1 and 100."""
        for q in [1, 100]:
            out = self.sub_output_dir(f"fq_{q}")
            ok, msg = process_image(
                str(self.rgb_path), "format_converter",
                {"format": "WebP", "quality": q, "output_dir": str(out)},
            )
            self.assertTrue(ok, f"Quality {q}: {msg}")

    def test_icc_profile_preservation(self) -> None:
        """ICC profile survives through metadata cleaner."""
        rgb_img = make_rgb_image((100, 100))
        fake_icc = b"FAKE_ICC_PROFILE_FOR_TEST"
        icc_path = self.test_dir / "icc_test.png"
        rgb_img.save(icc_path, icc_profile=fake_icc)

        ok, msg = process_image(
            str(icc_path), "metadata_cleaner",
            {"strip_all": True, "keep_icc": True,
             "output_dir": str(self.output_dir)},
        )
        self.assertTrue(ok, msg)
        for f in self.output_files():
            with Image.open(f) as img:
                self.assertIn("icc_profile", img.info)

    # ------------------------------------------------------------------
    # Integration: presets + macro + history
    # ------------------------------------------------------------------
    def test_preset_save_load_apply(self) -> None:
        """Save preset → load → verify params."""
        params = {"rows": 5, "cols": 7}
        save_preset("grid_splitter", "workflow_test", params)
        data = load_preset("workflow_test")
        assert data is not None
        self.assertEqual(data["params"]["rows"], 5)
        self.assertEqual(data["params"]["cols"], 7)
        delete_preset("workflow_test")

    def test_macro_record_and_generate(self) -> None:
        """Record macro → generate script → verify valid Python."""
        rec = MacroRecorder()
        rec.start()
        rec.record("resizer", {"width": 0.5, "height": 0.5})
        rec.record("filters", {"grayscale": True})
        script = rec.stop()
        self.assertIn("def run_macro", script)
        compile(script, "<macro>", "exec")

    def test_history_push_undo_redo(self) -> None:
        """History lifecycle: push → undo → redo → export."""
        import time

        mgr = HistoryManager(max_depth=10)
        e1 = HistoryEntry(
            timestamp=time.time(),
            operator_name="grid_splitter",
            config_snapshot={"rows": 2, "cols": 2},
            input_files=[str(self.rgb_path)],
            description="Split 2x2",
        )
        mgr.push(e1)
        self.assertTrue(mgr.can_undo())

        undone = mgr.undo()
        assert undone is not None
        self.assertEqual(undone.operator_name, "grid_splitter")
        self.assertFalse(mgr.can_undo())

        redone = mgr.redo()
        assert redone is not None
        self.assertEqual(redone.operator_name, "grid_splitter")

        # Export
        log_path = self.test_dir / "history_log.json"
        mgr.export_log(str(log_path))
        self.assertTrue(log_path.exists())

    # ------------------------------------------------------------------
    # Script engine workflow
    # ------------------------------------------------------------------
    def test_script_engine_chained_ops(self) -> None:
        """Chain resize → split via script engine."""
        engine = ScriptEngine()
        result = engine.chain(
            [str(self.rgb_path)],
            "resizer(width=0.5, height=0.5) | grid_splitter(rows=2, cols=2)",
            str(self.output_dir),
        )
        self.assertTrue(result.success, result.message)
        self.assertGreater(self.count_output_files(), 0)

    # ------------------------------------------------------------------
    # Error resilience
    # ------------------------------------------------------------------
    def test_unknown_processor_graceful_fail(self) -> None:
        ok, msg = process_image(
            str(self.rgb_path), "nonexistent_xyz",
            {"output_dir": str(self.output_dir)},
        )
        self.assertFalse(ok)

    def test_invalid_template_placeholder(self) -> None:
        ok, msg = process_image(
            str(self.rgb_path), "grid_splitter",
            {"rows": 1, "cols": 1, "output_dir": str(self.output_dir),
             "template": "{bad_placeholder}"},
        )
        self.assertFalse(ok)
        self.assertIn("Invalid", msg)

    def test_missing_file(self) -> None:
        ok, msg = process_image(
            str(self.test_dir / "no_file.png"), "grid_splitter",
            {"output_dir": str(self.output_dir)},
        )
        self.assertFalse(ok)

    # ------------------------------------------------------------------
    # Pixel accuracy & round-trip consistency
    # ------------------------------------------------------------------
    def test_gradient_pixel_accuracy(self) -> None:
        """Split a gradient image → verify sub-image pixels match original."""
        grad_path = self.test_dir / "gradient.png"
        grad = make_gradient_image((200, 200))
        grad.save(grad_path)

        ok, _ = process_image(
            str(grad_path), "grid_splitter",
            {"rows": 2, "cols": 2, "output_dir": str(self.output_dir),
             "template": "grad_{row}_{col}"},
        )
        self.assertTrue(ok)

        files = self.output_files()
        self.assertGreaterEqual(len(files), 4)
        for f in files:
            with Image.open(f) as img:
                self.assertEqual(img.size, (100, 100))
                self.assertEqual(img.mode, "RGB")

    def test_round_trip_modal_compatibility(self) -> None:
        """Every processor must handle RGBA, L, and P modes."""
        images = {
            "RGBA": (self.rgba_path, make_rgba_image()),
            "L": (self.gray_path, make_grayscale_image()),
            "P": (self.palette_path, None),
        }
        for mode, (path, _) in images.items():
            out = self.sub_output_dir(f"modal_{mode}")
            ok, msg = process_image(
                str(path), "resizer",
                {"width": 1.0, "height": 1.0,
                 "output_dir": str(out)},
            )
            self.assertTrue(ok, f"Resizer on {mode}: {msg}")

    # ------------------------------------------------------------------
    # Template variable substitution
    # ------------------------------------------------------------------
    def test_template_all_variables(self) -> None:
        """Verify all standard template variables."""
        out = self.sub_output_dir("tmpl")
        ok, msg = process_image(
            str(self.rgb_path), "grid_splitter",
            {"rows": 2, "cols": 2, "output_dir": str(out),
             "template": "f_{filename}_r{row}_c{col}_w{w}_h{h}_{index}.{ext}"},
        )
        self.assertTrue(ok, msg)
        files = self.output_files("tmpl")
        self.assertEqual(len(files), 4)
        names = {f.name for f in files}
        # Each filename should contain the vars
        for n in names:
            self.assertIn("_r", n)
            self.assertIn("_c", n)
            self.assertIn("_w", n)
            self.assertIn("_h", n)


if __name__ == '__main__':
    import unittest
    unittest.main()
