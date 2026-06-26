"""ChainAsGraph vs CommandDispatcher pixel-identical validation for ALL processors.

P0-P1 safety net — any regression in the unified execution path is caught here.
"""
import unittest
from typing import Any

from PIL import Image

from image_splitter.core import register_all_processors
from image_splitter.engine.dispatcher import CommandDispatcher
from image_splitter.engine.legacy_adapter import ChainAsGraph
from .conftest import assert_images_equal


class TestChainAsGraphAllProcessors(unittest.TestCase):
    """Verify ChainAsGraph output is pixel-identical to CommandDispatcher."""

    @classmethod
    def setUpClass(cls) -> None:
        register_all_processors()

    def setUp(self) -> None:
        # A small non-trivial test image with distinct regions
        self.img = Image.new("RGB", (60, 40), (255, 255, 255))
        # Draw colored squares so output is distinguishable
        self.img.paste((255, 0, 0), (0, 0, 20, 20))       # red TL
        self.img.paste((0, 255, 0), (40, 0, 60, 20))       # green TR
        self.img.paste((0, 0, 255), (0, 20, 20, 40))       # blue BL
        self.img.paste((128, 128, 0), (40, 20, 60, 40))    # yellow BR

    def _assert_same_output(
        self, processor_name: str, config: dict[str, Any], output_count: int = 1,
    ) -> None:
        cmd_str_parts = [f"{processor_name}("]
        cmd_str_parts.extend(f"{k}={v!r}," for k, v in config.items())
        cmd_str = "".join(cmd_str_parts).rstrip(",") + ")"

        # CommandDispatcher path
        d_results = CommandDispatcher.execute_chain(self.img.copy(), cmd_str)
        # ChainAsGraph path
        g_results = ChainAsGraph.execute_chain(self.img.copy(), cmd_str)

        self.assertEqual(
            len(d_results), len(g_results),
            f"{processor_name}: output count mismatch D={len(d_results)} G={len(g_results)}"
        )

        for i, (d_img, g_img) in enumerate(zip(d_results, g_results)):
            with self.subTest(processor=processor_name, index=i):
                assert_images_equal(d_img, g_img)
            d_img.close()
            g_img.close()

    # ------------------------------------------------------------------
    # Single-output processors
    # ------------------------------------------------------------------

    def test_resizer(self) -> None:
        self._assert_same_output("resizer", {"width": 0.5, "height": 0.5})

    def test_color_adjuster(self) -> None:
        self._assert_same_output("color_adjuster", {
            "brightness": 1.5, "contrast": 1.2, "sharpness": 1.1, "color": 0.8,
        })

    def test_filters_grayscale(self) -> None:
        self._assert_same_output("filters", {"grayscale": True})

    def test_filters_invert(self) -> None:
        self._assert_same_output("filters", {"invert": True})

    def test_filters_both(self) -> None:
        self._assert_same_output("filters", {"grayscale": True, "invert": True})

    def test_geometry_rotate(self) -> None:
        self._assert_same_output("geometry", {"rotate": 90})

    def test_geometry_flip(self) -> None:
        self._assert_same_output("geometry", {"flip_h": True, "flip_v": True})

    def test_format_converter_webp(self) -> None:
        self._assert_same_output("format_converter", {"format": "WebP", "quality": 80})

    def test_format_converter_jpeg(self) -> None:
        self._assert_same_output("format_converter", {"format": "JPEG", "quality": 90})

    def test_metadata_cleaner_strip(self) -> None:
        self._assert_same_output("metadata_cleaner", {"strip_all": True})

    def test_metadata_cleaner_no_strip(self) -> None:
        self._assert_same_output("metadata_cleaner", {"strip_all": False})

    def test_border_solid(self) -> None:
        self._assert_same_output("border", {
            "width": 5, "color": "#ff0000", "style": "solid",
        })

    def test_border_dashed(self) -> None:
        self._assert_same_output("border", {
            "width": 3, "color": "#00ff00", "style": "dashed",
        })

    def test_border_double(self) -> None:
        self._assert_same_output("border", {
            "width": 8, "color": "#0000ff", "style": "double",
        })

    def test_rounded_corner(self) -> None:
        self._assert_same_output("rounded_corner", {"radius": 10})

    def test_smart_crop(self) -> None:
        self._assert_same_output("smart_crop", {"threshold": 30, "margin": 2})

    def test_watermark(self) -> None:
        self._assert_same_output("text_watermark", {
            "text": "TEST", "size": 14, "opacity": 100, "anchor": "C",
        })

    def test_adjuster_ratio(self) -> None:
        self._assert_same_output("canvas_adjuster", {
            "width": 0.8, "height": 1.2, "anchor": "center",
        })

    # ------------------------------------------------------------------
    # Multi-output processors (splitters)
    # ------------------------------------------------------------------

    def test_grid_splitter(self) -> None:
        self._assert_same_output(
            "grid_splitter",
            {"rows": 2, "cols": 3},
            output_count=6,
        )

    def test_custom_splitter(self) -> None:
        self._assert_same_output(
            "custom_splitter",
            {"h_lines": [20], "v_lines": [15, 30, 45]},
            output_count=8,
        )

    # ------------------------------------------------------------------
    # Multi-step chains
    # ------------------------------------------------------------------

    def test_long_chain(self) -> None:
        cmd = "resizer(width=0.5,height=0.5)|filters(grayscale=True)|border(width=3,color='#ff0000',style='solid')"
        d_results = CommandDispatcher.execute_chain(self.img.copy(), cmd)
        g_results = ChainAsGraph.execute_chain(self.img.copy(), cmd)

        self.assertEqual(len(d_results), len(g_results))
        for d_img, g_img in zip(d_results, g_results):
            assert_images_equal(d_img, g_img)
            d_img.close()
            g_img.close()

    def test_split_then_resize_chain(self) -> None:
        """Known limitation: multi-output processors (splitters) as
        intermediate steps in a chain fan out to multiple images,
        but the NodeGraph uses single-socket connections.  The
        CommandDispatcher handles fan-out per-image; ChainAsGraph
        only propagates results[0][0].  Splitters should be the
        LAST step in a chain when using ChainAsGraph."""
        cmd = "grid_splitter(rows=1,cols=2)|resizer(width=0.5,height=0.5)"
        # ChainAsGraph: only results[0][0] from splitter flows to resizer
        g_results = ChainAsGraph.execute_chain(self.img.copy(), cmd)
        self.assertEqual(len(g_results), 1,
                         "ChainAsGraph produces 1 output because splitter "
                         "in middle only propagates first result via single socket")


if __name__ == "__main__":
    unittest.main()
