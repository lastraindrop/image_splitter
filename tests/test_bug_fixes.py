# image_splitter/tests/test_bug_fixes.py
"""Verification tests for all confirmed bug fixes."""
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from image_splitter.core import process_image, register_all_processors
from image_splitter.engine.registry import ProcessorRegistry
from image_splitter.models import ResizeConfig


class TestBugFixes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        register_all_processors()

    def setUp(self):
        self._temp_dir_obj = tempfile.TemporaryDirectory()
        self.test_dir = Path(self._temp_dir_obj.name).resolve()
        self.output_dir = self.test_dir / "output"
        self.output_dir.mkdir(exist_ok=True)
        self.img_path = self.test_dir / "test.png"
        Image.new("RGB", (100, 100), color="red").save(self.img_path)
        self.rgba_path = self.test_dir / "test_rgba.png"
        Image.new("RGBA", (100, 100), color=(255, 0, 0, 128)).save(self.rgba_path)

    def tearDown(self):
        self._temp_dir_obj.cleanup()

    def test_bug01_watermark_returns_result(self):
        """BUG-01: watermark process() must return List[Tuple[Image, Dict]]."""
        config = {
            "text": "TEST",
            "opacity": 128,
            "size": 20,
            "anchor": "BR",
            "output_dir": str(self.output_dir),
        }
        success, msg = process_image(str(self.rgba_path), "text_watermark", config)
        self.assertTrue(success, f"Watermark processing failed: {msg}")
        files = list(self.output_dir.glob("*.png"))
        self.assertGreater(len(files), 0)

    def test_bug01_watermark_produces_rgba_output(self):
        """Watermark output must preserve alpha channel."""
        config = {
            "text": "WATERMARK",
            "opacity": 200,
            "anchor": "C",
            "output_dir": str(self.output_dir),
            "template": "wm_test",
        }
        success, msg = process_image(str(self.rgba_path), "text_watermark", config)
        self.assertTrue(success, msg)
        with Image.open(self.output_dir / "wm_test.png") as img:
            self.assertEqual(img.mode, "RGBA")

    def test_bug02_resizer_config_model_rejects_zero(self):
        """ResizeConfig must reject zero or negative ratios (Fail-Fast)."""
        with self.assertRaises(ValueError):
            ResizeConfig(width=0, height=1.0)
        with self.assertRaises(ValueError):
            ResizeConfig(width=1.0, height=-0.5)
        with self.assertRaises(ValueError):
            ResizeConfig(width=0.0, height=0.0)

    def test_bug02_resizer_valid_config_passes(self):
        """Valid resize config should pass validation."""
        config = ResizeConfig(width=0.5, height=2.0)
        self.assertEqual(config.width, 0.5)
        self.assertEqual(config.height, 2.0)

    def test_bug03_geometry_rejects_invalid_angle(self):
        """geometry processor must reject non-standard rotation angles."""
        config = {
            "rotate": "45",
            "flip_h": False,
            "flip_v": False,
            "output_dir": str(self.output_dir),
        }
        success, msg = process_image(str(self.img_path), "geometry", config)
        self.assertFalse(success)
        self.assertTrue(
            "Unsupported rotation angle" in msg or "requires enum" in msg,
            f"Expected rejection of angle 45, got: {msg}"
        )

    def test_bug03_geometry_accepts_standard_angles(self):
        """geometry processor must accept 0/90/180/270."""
        for angle in ["0", "90", "180", "270"]:
            with self.subTest(angle=angle):
                out_sub = self.output_dir / angle
                out_sub.mkdir(exist_ok=True)
                config = {
                    "rotate": angle,
                    "output_dir": str(out_sub),
                    "template": f"rot_{angle}",
                }
                success, msg = process_image(str(self.img_path), "geometry", config)
                self.assertTrue(success, f"Angle {angle} failed: {msg}")

    def test_bug04_processors_init_exports_all(self):
        """All 10 processors must be importable from processors package."""
        from image_splitter.processors import (
            GridSplitter, ImageResizer, CustomLineSplitter, CanvasAdjuster,
            ImageColorAdjuster, SimpleFilterProcessor, ImageFormatConverter,
            GeometryProcessor, MetadataProcessor, TextWatermark,
        )
        classes = [
            GridSplitter, ImageResizer, CustomLineSplitter, CanvasAdjuster,
            ImageColorAdjuster, SimpleFilterProcessor, ImageFormatConverter,
            GeometryProcessor, MetadataProcessor, TextWatermark,
        ]
        self.assertEqual(len(classes), 10)

    def test_bug05_metadata_palette_mode_handling(self):
        """metadata_cleaner must handle P-mode images without color corruption."""
        img = Image.new("P", (50, 50))
        palette = [i % 256 for i in range(768)]
        img.putpalette(palette)
        p_path = self.test_dir / "palette.png"
        img.save(p_path)

        config = {
            "strip_all": True,
            "keep_icc": False,
            "output_dir": str(self.output_dir),
            "template": "palette_clean",
        }
        success, msg = process_image(str(p_path), "metadata_cleaner", config)
        self.assertTrue(success, msg)

    def test_bug06_cli_set_type_coercion(self):
        """CLI --set values must be coerced to correct types via processor metadata."""
        processor = ProcessorRegistry.get("grid_splitter")
        from image_splitter.engine.config_coercion import coerce_processor_config
        raw = {"rows": "3", "cols": "2"}
        coerced = coerce_processor_config(processor, raw)
        self.assertIsInstance(coerced["rows"], int)
        self.assertIsInstance(coerced["cols"], int)
        self.assertEqual(coerced["rows"], 3)
        self.assertEqual(coerced["cols"], 2)

    def test_bug07_watermark_all_anchors_produce_output(self):
        """Watermark must work for all 5 anchor positions."""
        for anchor in ["TL", "TR", "BL", "BR", "C"]:
            with self.subTest(anchor=anchor):
                out_sub = self.output_dir / anchor
                out_sub.mkdir(exist_ok=True)
                config = {
                    "text": f"WM_{anchor}",
                    "anchor": anchor,
                    "opacity": 128,
                    "output_dir": str(out_sub),
                    "template": f"wm_{anchor}",
                }
                success, msg = process_image(str(self.rgba_path), "text_watermark", config)
                self.assertTrue(success, f"Anchor {anchor} failed: {msg}")

    def test_bug13_keymap_uses_tkinter_format(self):
        """BUG-13: DEFAULT_KEYMAP must use tkinter-compatible key sequences."""
        from image_splitter.keymap import DEFAULT_KEYMAP
        global_binds = DEFAULT_KEYMAP.get("global", {})
        for key_seq in global_binds:
            self.assertFalse(
                key_seq.startswith("<Ctrl-"),
                f"Key '{key_seq}' uses <Ctrl-> format; "
                f"tkinter expects <Control-> format"
            )
        self.assertIn("<Control-o>", global_binds)
        self.assertIn("<Control-Return>", global_binds)
        self.assertIn("<Delete>", global_binds)

    def test_bug14_delete_keybind_does_not_override_keymap(self):
        """BUG-14: <Delete> must be bound on file_listbox, not root."""
        try:
            import tkinter as tk
        except ImportError:
            self.skipTest("tkinter not available")
        try:
            root = tk.Tk()
            root.withdraw()
        except Exception:
            self.skipTest("Tk display not available")
        try:
            from image_splitter.gui import ImageSplitterApp
            app = ImageSplitterApp(root)
            root_binds = root.bind()
            root_delete_binds = [
                b for b in root_binds if b == "<Delete>"
            ]
            self.assertEqual(
                len(root_delete_binds), 0,
                "root should not have a direct <Delete> binding; "
                "it should only be on file_listbox via keymap"
            )
        finally:
            root.destroy()

    def test_bug15_on_file_selected_opens_image_once(self):
        """BUG-15: _on_file_selected should only open image once."""
        try:
            import tkinter as tk
        except ImportError:
            self.skipTest("tkinter not available")
        try:
            root = tk.Tk()
            root.withdraw()
        except Exception:
            self.skipTest("Tk display not available")
        from unittest.mock import patch, MagicMock
        try:
            from image_splitter.gui import ImageSplitterApp
            app = ImageSplitterApp(root)
            app.current_files = [str(self.img_path)]
            app.file_listbox.insert(tk.END, self.img_path.name)
            app.file_listbox.selection_set(0)
            with patch("image_splitter.gui.Image.open") as mock_open:
                mock_img = MagicMock()
                mock_img.__enter__ = MagicMock(return_value=mock_img)
                mock_img.__exit__ = MagicMock(return_value=False)
                mock_img.size = (100, 100)
                mock_img.convert.return_value = mock_img
                mock_img.thumbnail = MagicMock()
                app._on_file_selected()
                self.assertEqual(mock_open.call_count, 1,
                                 "Image.open should be called exactly once")
        finally:
            root.destroy()

    def test_bug16_icc_profile_preserved_after_crop(self):
        """BUG-16: ICC profile must survive through crop/split operations."""
        import io
        rgb_img = Image.new("RGB", (200, 200), "red")
        fake_icc = b"FAKE_ICC_PROFILE_DATA"
        rgb_img.info["icc_profile"] = fake_icc
        ico_path = self.test_dir / "icc_test.png"
        rgb_img.save(ico_path, icc_profile=fake_icc)

        out_sub = self.output_dir / "icc_split"
        out_sub.mkdir(exist_ok=True)
        config = {
            "rows": 2,
            "cols": 2,
            "output_dir": str(out_sub),
            "template": "{filename}_{row}_{col}",
        }
        success, msg = process_image(str(ico_path), "grid_splitter", config)
        self.assertTrue(success, msg)
        saved_files = list(out_sub.glob("*.png"))
        self.assertGreater(len(saved_files), 0)
        for f in saved_files:
            with Image.open(f) as result:
                self.assertIn("icc_profile", result.info,
                              f"ICC profile lost in {f.name}")

    def test_bug17_script_engine_output_collection(self):
        """BUG-17: script_engine.process must collect only new output files."""
        from image_splitter.script_engine import ScriptEngine
        engine = ScriptEngine()
        result = engine.process(
            [str(self.img_path)],
            "grid_splitter",
            {"rows": 2, "cols": 2, "output_dir": str(self.output_dir)}
        )
        self.assertTrue(result.success)
        self.assertGreater(len(result.output_files), 0,
                           "Output files should be collected")
        for f in result.output_files:
            self.assertTrue(f.exists(), f"Output file {f} should exist")

    def test_bug18_keymap_imports_settings_config_dir(self):
        """BUG-18: keymap should reuse settings.get_config_dir()."""
        from image_splitter import keymap, settings
        km_dir = keymap.get_keymap_path().parent
        s_dir = settings.get_config_dir()
        self.assertEqual(km_dir, s_dir)

    def test_bug19_geometry_config_validates_angle(self):
        """GeometryConfig must reject invalid rotation angles."""
        from image_splitter.models import GeometryConfig
        with self.assertRaises(ValueError):
            GeometryConfig(rotate=45)
        with self.assertRaises(ValueError):
            GeometryConfig(rotate=-90)
        config = GeometryConfig(rotate=90)
        self.assertEqual(config.rotate, 90)

    def test_bug19_format_config_validates_format(self):
        """FormatConfig must reject unsupported formats and invalid quality."""
        from image_splitter.models import FormatConfig
        with self.assertRaises(ValueError):
            FormatConfig(format="TIFF")
        with self.assertRaises(ValueError):
            FormatConfig(quality=0)
        with self.assertRaises(ValueError):
            FormatConfig(quality=101)
        config = FormatConfig(format="WebP", quality=80)
        self.assertEqual(config.format, "WebP")

    def test_bug19_watermark_config_validates_params(self):
        """WatermarkConfig must validate size, opacity, and anchor."""
        from image_splitter.models import WatermarkConfig
        with self.assertRaises(ValueError):
            WatermarkConfig(size=0)
        with self.assertRaises(ValueError):
            WatermarkConfig(opacity=256)
        with self.assertRaises(ValueError):
            WatermarkConfig(anchor="XX")
        config = WatermarkConfig(text="test", size=20, opacity=128, anchor="TL")
        self.assertEqual(config.anchor, "TL")

    def test_bug20_prepare_image_for_save_handles_bmp(self):
        """_prepare_image_for_save must flatten transparency for BMP format."""
        from image_splitter.core import _prepare_image_for_save
        rgba = Image.new("RGBA", (10, 10), (255, 0, 0, 128))
        result = _prepare_image_for_save(rgba, "BMP")
        self.assertEqual(result.mode, "RGB")

    def test_bug21_logging_not_configured_on_import(self):
        """Importing image_splitter must not configure logging as side effect."""
        import importlib
        import image_splitter
        import logging
        root_logger = logging.getLogger()
        handlers_before = len(root_logger.handlers)
        importlib.reload(image_splitter)
        root_logger_after = logging.getLogger()
        handlers_after = len(root_logger_after.handlers)
        self.assertEqual(handlers_before, handlers_after,
                         "Importing should not add log handlers")

    def test_bug29_watermark_cross_platform_font(self):
        """BUG-29: Watermark must not crash on non-Windows platforms."""
        from image_splitter.processors.watermark import TextWatermark
        proc = TextWatermark()
        img = Image.new("RGBA", (100, 100), (255, 255, 255, 255))
        config = {"text": "FONT_TEST", "size": 30, "opacity": 128, "anchor": "C"}
        results = proc.process(img, config)
        self.assertEqual(len(results), 1)
        result_img, ctx = results[0]
        self.assertEqual(result_img.mode, "RGBA")

    def test_bug30_console_execute_uses_thread(self):
        """BUG-30: Console execute must not block GUI thread."""
        try:
            import tkinter as tk
        except ImportError:
            self.skipTest("tkinter not available")
        try:
            root = tk.Tk()
            root.withdraw()
        except Exception:
            self.skipTest("Tk display not available")
        from unittest.mock import MagicMock, patch
        try:
            from image_splitter.gui import ImageSplitterApp
            app = ImageSplitterApp(root)
            app.current_files = [str(self.img_path)]
            with patch("image_splitter.gui.threading.Thread") as mock_thread:
                mock_thread_instance = MagicMock()
                mock_thread.return_value = mock_thread_instance
                app._console_execute("grid_splitter", {"rows": 2, "cols": 2})
                mock_thread.assert_called_once()
                mock_thread_instance.start.assert_called_once()
        finally:
            root.destroy()

    def test_bug34_filters_p_mode_invert(self):
        """BUG-34: Invert filter must handle P-mode images without crash."""
        img = Image.new("P", (50, 50))
        palette = [i % 256 for i in range(768)]
        img.putpalette(palette)
        p_path = self.test_dir / "p_mode_invert.png"
        img.save(p_path)
        config = {
            "grayscale": False,
            "invert": True,
            "output_dir": str(self.output_dir),
            "template": "p_invert",
        }
        success, msg = process_image(str(p_path), "filters", config)
        self.assertTrue(success, f"P-mode invert failed: {msg}")

    def test_bug36_chain_passes_extra_config(self):
        """BUG-36: execute_chain must accept extra_config parameter."""
        from image_splitter.engine.dispatcher import CommandDispatcher
        img = Image.new("RGB", (100, 100), "blue")
        extra = {"custom_key": "custom_value"}
        result = CommandDispatcher.execute_chain(
            img, "resizer(width=0.5,height=0.5)", extra_config=extra
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].size, (50, 50))
        result[0].close()

    def test_bug39_all_config_models_exported(self):
        """BUG-39: All config models must be importable from package __init__."""
        import image_splitter
        for name in [
            "SplitConfig", "AdjustConfig", "CustomSplitConfig", "ResizeConfig",
            "ColorConfig", "FilterConfig", "FormatConfig", "GeometryConfig",
            "MetadataConfig", "WatermarkConfig",
        ]:
            self.assertTrue(
                hasattr(image_splitter, name),
                f"{name} should be exported from image_splitter.__init__"
            )

    def test_bug40_registry_duplicate_name_warning(self):
        """BUG-40: Registering duplicate processor name should warn, not silently overwrite."""
        import logging
        from image_splitter.engine.registry import ProcessorRegistry
        from image_splitter.engine.base import BaseProcessor

        class FakeProcessor(BaseProcessor):
            @property
            def name(self):
                return "_test_duplicate"

            @property
            def display_name(self):
                return "Test Duplicate"

            def process(self, image, config):
                return [(image.copy(), {})]

        ProcessorRegistry.reset()
        with self.assertLogs("image_splitter.engine.registry", level="WARNING") as cm:
            fake1 = FakeProcessor()
            fake2 = FakeProcessor()
            ProcessorRegistry.register(fake1)
            ProcessorRegistry.register(fake2)
            self.assertTrue(
                any("re-registered" in msg for msg in cm.output),
                f"Expected re-registration warning, got: {cm.output}"
            )
        ProcessorRegistry.reset()
        register_all_processors()

    def test_bug27_macro_write_error_handling(self):
        """BUG-27: Macro save returns False for empty recording."""
        from image_splitter.engine.macro import MacroRecorder
        recorder = MacroRecorder()
        recorder.start()
        result = recorder.save(self.test_dir / "empty_macro.py")
        self.assertFalse(result, "Empty recording save should return False")

    def test_bug38_preview_ratio_zero_origin_guard(self):
        """BUG-38: _render_canvas must guard against zero-size origin."""
        try:
            import tkinter as tk
        except ImportError:
            self.skipTest("tkinter not available")
        try:
            root = tk.Tk()
            root.withdraw()
        except Exception:
            self.skipTest("Tk display not available")
        from unittest.mock import MagicMock
        try:
            from image_splitter.gui import ImageSplitterApp
            app = ImageSplitterApp(root)
            app.current_orig_size = (0, 0)
            app.thumb_img = Image.new("RGB", (10, 10))
            app.canvas.winfo_width = MagicMock(return_value=500)
            app.canvas.winfo_height = MagicMock(return_value=500)
            app._render_canvas()
        finally:
            root.destroy()

    def test_bug32_no_module_reload_on_discovery(self):
        """BUG-32: Module reload should not occur for already-loaded modules."""
        import importlib
        from unittest.mock import patch
        with patch("importlib.reload") as mock_reload:
            register_all_processors()
            mock_reload.assert_not_called()


if __name__ == "__main__":
    unittest.main()
