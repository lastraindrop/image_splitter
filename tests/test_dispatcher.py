"""Tests for command dispatcher."""

import unittest

from PIL import Image

from image_splitter.engine.dispatcher import CommandDispatcher
from image_splitter.engine.registry import ProcessorRegistry

class TestDispatcher(unittest.TestCase):
    def test_parse_simple(self):
        cmd = "grid_splitter(rows=3, cols=2)"
        ops = CommandDispatcher.parse_command(cmd)
        self.assertEqual(len(ops), 1)
        self.assertEqual(ops[0][0], "grid_splitter")
        self.assertEqual(ops[0][1]["rows"], 3)
        self.assertEqual(ops[0][1]["cols"], 2)

    def test_parse_complex_literals(self):
        cmd = "custom_splitter(h_lines=[20, 80], v_lines=[30]) | grid_splitter(offsets=(1, 2, 3, 4)) | text_watermark(text='A,B', anchor='BR')"
        ops = CommandDispatcher.parse_command(cmd)
        self.assertEqual(ops[0][1]["h_lines"], [20, 80])
        self.assertEqual(ops[0][1]["v_lines"], [30])
        self.assertEqual(ops[1][1]["offsets"], (1, 2, 3, 4))
        self.assertEqual(ops[2][1]["text"], "A,B")
        self.assertEqual(ops[2][1]["anchor"], "BR")

    def test_execute_chain_mock(self):
        ProcessorRegistry.reset()
        # Create 100x100 image
        img = Image.new("RGB", (100, 100))
        # Chain call: first split into 2x2 (generating 50x50), 
        # logically the dispatcher currently returns all result images.
        # Note: execute_chain here returns a list of Images.
        cmd = "grid_splitter(rows=2, cols=2)"
        results = CommandDispatcher.execute_chain(img, cmd)
        self.assertEqual(len(results), 4)
        self.assertEqual(results[0].size, (50, 50))

if __name__ == '__main__':
    unittest.main()
