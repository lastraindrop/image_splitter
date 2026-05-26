"""Tests for command dispatcher — parsing, chaining, coercion, and resource safety."""
from PIL import Image

from image_splitter.engine.dispatcher import CommandDispatcher
from image_splitter.engine.registry import ProcessorRegistry

from .conftest import BaseTest


class TestDispatcherParsing(BaseTest):
    """Parse single and chained command strings."""

    def test_parse_simple(self) -> None:
        ops = CommandDispatcher.parse_command("grid_splitter(rows=3, cols=2)")
        self.assertEqual(len(ops), 1)
        self.assertEqual(ops[0][0], "grid_splitter")
        self.assertEqual(ops[0][1]["rows"], 3)
        self.assertEqual(ops[0][1]["cols"], 2)

    def test_parse_complex_literals(self) -> None:
        cmd = (
            "custom_splitter(h_lines=[20, 80], v_lines=[30]) | "
            "grid_splitter(offsets=(1, 2, 3, 4)) | "
            "text_watermark(text='A,B', anchor='BR')"
        )
        ops = CommandDispatcher.parse_command(cmd)
        self.assertEqual(ops[0][1]["h_lines"], [20, 80])
        self.assertEqual(ops[0][1]["v_lines"], [30])
        self.assertEqual(ops[1][1]["offsets"], (1, 2, 3, 4))
        self.assertEqual(ops[2][1]["text"], "A,B")
        self.assertEqual(ops[2][1]["anchor"], "BR")

    def test_parse_malformed_raises(self) -> None:
        with self.assertRaises(ValueError):
            CommandDispatcher.parse_command("bad_syntax(rows=3 cols=2)")

    def test_parse_empty(self) -> None:
        ops = CommandDispatcher.parse_command("")
        self.assertEqual(len(ops), 0)


class TestDispatcherChain(BaseTest):
    """Chain execution with type coercion and defaults."""

    def test_default_injection(self) -> None:
        img = Image.new("RGB", (100, 100))
        results = CommandDispatcher.execute_chain(img, "grid_splitter()")
        self.assertEqual(len(results), 9)  # 3x3 default

    def test_string_coercion(self) -> None:
        img = Image.new("RGB", (100, 100))
        results = CommandDispatcher.execute_chain(
            img, "grid_splitter(rows='2', cols=2)"
        )
        self.assertEqual(len(results), 4)

    def test_complex_chain(self) -> None:
        img = Image.new("RGB", (100, 100))
        results = CommandDispatcher.execute_chain(
            img,
            "resizer(width=0.5, height=0.5) | grid_splitter(rows=2, cols=2)",
        )
        self.assertEqual(len(results), 4)
        self.assertEqual(results[0].size, (25, 25))

    def test_chain_with_extra_config(self) -> None:
        img = Image.new("RGB", (100, 100))
        results = CommandDispatcher.execute_chain(
            img,
            "resizer(width=0.5, height=0.5)",
            extra_config={"custom": True},
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].size, (50, 50))

    def test_chain_resource_cleanup(self) -> None:
        """Intermediate images must be closed after chain."""
        img = Image.new("RGB", (100, 100))
        results = CommandDispatcher.execute_chain(
            img, "grid_splitter(rows=2, cols=2)"
        )
        # Final results should be openable images
        for r in results:
            self.assertIsInstance(r, Image.Image)
            r.close()


if __name__ == '__main__':
    import unittest
    unittest.main()
