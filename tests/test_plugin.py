"""Tests for the user plugin system and auto-discovery."""
from pathlib import Path

from PIL import Image

from image_splitter.core import process_image, register_all_processors
from image_splitter.engine.registry import ProcessorRegistry

from .conftest import BaseTest, WHITE, make_rgb_image


class TestPluginSystem(BaseTest):
    """Plugin discovery, metadata, and functional tests."""

    def test_plugins_package_is_importable(self) -> None:
        from image_splitter import plugins
        self.assertIsNotNone(plugins)

    def test_example_plugin_is_registered(self) -> None:
        names = [p.name for p in ProcessorRegistry.list_all()]
        self.assertIn("invert_color", names)

    def test_example_plugin_has_metadata(self) -> None:
        proc = ProcessorRegistry.get("invert_color")
        self.assertEqual(proc.name, "invert_color")
        self.assertEqual(proc.display_name, "Invert Colors (Plugin)")
        self.assertEqual(proc.category, "Filter")
        self.assertTrue(len(proc.tool_tip) > 0)
        meta = proc.get_ui_metadata()
        self.assertEqual(len(meta), 1)
        self.assertEqual(meta[0]["name"], "invert_alpha")
        self.assertEqual(meta[0]["type"], "bool")

    def test_example_plugin_inverts_colors(self) -> None:
        proc = ProcessorRegistry.get("invert_color")
        img = make_rgb_image((10, 10), WHITE)
        result = proc.process(img, {})
        self.assertEqual(len(result), 1)
        out_img, ctx = result[0]
        self.assertEqual(ctx["action"], "inverted")
        self.assertEqual(out_img.getpixel((0, 0)), (0, 0, 0))

    def test_total_processor_count_includes_plugin(self) -> None:
        """Plugin is among registered processors (count >= 11)."""
        by_category: dict[str, list[str]] = {}
        for p in ProcessorRegistry.list_all():
            by_category.setdefault(p.category, []).append(p.name)
        # Expected: at least "Split", "Transform", "Edit", "Filter" (plugin), "Export"
        self.assertIn("Filter", by_category)
        self.assertIn("invert_color", by_category["Filter"])
        self.assertGreaterEqual(
            len(ProcessorRegistry.list_all()), 11,
            f"Expected at least 11 processors, got {len(ProcessorRegistry.list_all())}"
        )

    def test_plugin_smoke_with_process_image(self) -> None:
        out = self.sub_output_dir("plugin_smoke")
        # Use a white image so invert produces black
        white_path = self.test_dir / "white.png"
        make_rgb_image((20, 20), WHITE).save(white_path)
        ok, msg = process_image(
            str(white_path), "invert_color",
            {"output_dir": str(out)},
        )
        self.assertTrue(ok, msg)
        files = list(out.glob("*.png"))
        self.assertEqual(len(files), 1)
        with Image.open(files[0]) as result:
            self.assertEqual(result.getpixel((0, 0)), (0, 0, 0))


if __name__ == "__main__":
    import unittest
    unittest.main()
