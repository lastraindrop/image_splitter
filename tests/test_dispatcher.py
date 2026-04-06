# image_splitter/tests/test_dispatcher.py
import unittest
from PIL import Image
from engine.dispatcher import CommandDispatcher
from core import split_image_core # 确保注册了处理器

class TestDispatcher(unittest.TestCase):
    def test_parse_simple(self):
        cmd = "grid_splitter(rows=3, cols=2)"
        ops = CommandDispatcher.parse_command(cmd)
        self.assertEqual(len(ops), 1)
        self.assertEqual(ops[0][0], "grid_splitter")
        self.assertEqual(ops[0][1]["rows"], 3)
        self.assertEqual(ops[0][1]["cols"], 2)

    def test_execute_chain_mock(self):
        # 创建 100x100 图片
        img = Image.new("RGB", (100, 100))
        # 链式调用: 先切成 2x2 (生成 50x50)，逻辑上分发器目前会返回所有结果图片
        # 注意: 这里的 execute_chain 会返回一个 Image 列表
        cmd = "grid_splitter(rows=2, cols=2)"
        results = CommandDispatcher.execute_chain(img, cmd)
        self.assertEqual(len(results), 4)
        self.assertEqual(results[0].size, (50, 50))

if __name__ == '__main__':
    unittest.main()
