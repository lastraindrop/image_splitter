# image_splitter/tests/test_custom_splitter.py
import unittest
import os
import tempfile
from PIL import Image
from pathlib import Path
from models import CustomSplitConfig
from core import process_image

class TestCustomSplitter(unittest.TestCase):
    def setUp(self):
        self._temp_dir_obj = tempfile.TemporaryDirectory()
        self.test_dir = Path(self._temp_dir_obj.name).resolve()
        self.output_dir = self.test_dir / "output"
        self.output_dir.mkdir(exist_ok=True)
        
        # 创建一个 100x100 的测试图
        self.img_path = self.test_dir / "test_100.png"
        Image.new("RGB", (100, 100), color="white").save(self.img_path)

    def tearDown(self):
        self._temp_dir_obj.cleanup()

    def test_custom_split_simple(self):
        """测试简单的十字交叉切割 (2x2)"""
        # 在 50, 50 处各切一刀
        config = CustomSplitConfig(
            h_lines=[50], 
            v_lines=[50], 
            output_dir=str(self.output_dir),
            template="{filename}_{row}_{col}"
        )
        
        success, msg = process_image(str(self.img_path), "custom_splitter", config)
        self.assertTrue(success, msg)
        
        # 验证文件
        files = list(self.output_dir.glob("*.png"))
        self.assertEqual(len(files), 4)
        
        # 验证左上角那块是否是 50x50
        with Image.open(self.output_dir / "test_100_1_1.png") as img:
            self.assertEqual(img.size, (50, 50))

    def test_custom_split_irregular(self):
        """测试不规则坐标切割"""
        # Y轴切割点: 20, 80 -> 生成区间 (0,20), (20,80), (80,100) -> 3行
        # X轴切割点: 30 -> 生成区间 (0,30), (30,100) -> 2列
        # 总计 3x2 = 6 块
        config = CustomSplitConfig(
            h_lines=[20, 80],
            v_lines=[30],
            output_dir=str(self.output_dir)
        )
        
        success, _ = process_image(str(self.img_path), "custom_splitter", config)
        self.assertTrue(success)
        
        files = list(self.output_dir.glob("*.png"))
        self.assertEqual(len(files), 6)

    def test_custom_split_out_of_bounds(self):
        """测试超出范围的线应被忽略"""
        config = CustomSplitConfig(
            h_lines=[150], # 超出 100
            v_lines=[-10], # 负数由 validate 拦截或 processor 过滤
            output_dir=str(self.output_dir)
        )
        
        success, _ = process_image(str(self.img_path), "custom_splitter", config)
        self.assertTrue(success)
        # 只有一张图 (1x1)
        files = list(self.output_dir.glob("*.png"))
        self.assertEqual(len(files), 1)

if __name__ == '__main__':
    unittest.main()
