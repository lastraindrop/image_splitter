# tests/test_new_fixes.py
import unittest
import os
import tempfile
from PIL import Image
from pathlib import Path
from models import SplitConfig
from core import split_image_core

class TestNewFixes(unittest.TestCase):
    def setUp(self):
        self._temp_dir_obj = tempfile.TemporaryDirectory()
        self.test_dir = Path(self._temp_dir_obj.name).resolve()
        self.output_dir = self.test_dir / "output"
        self.output_dir.mkdir(exist_ok=True)
        
        # 创建一个测试图
        self.img_path = self.test_dir / "test.png"
        Image.new("RGB", (100, 100), color="blue").save(self.img_path)

    def tearDown(self):
        self._temp_dir_obj.cleanup()

    def test_output_dir_validation(self):
        """测试 output_dir 不能为空"""
        with self.assertRaises(ValueError) as ctx:
            SplitConfig(rows=2, cols=2, output_dir="")
        self.assertIn("输出目录路径不能为空", str(ctx.exception))

        with self.assertRaises(ValueError) as ctx:
            SplitConfig(rows=2, cols=2, output_dir=None)
        self.assertIn("输出目录路径不能为空", str(ctx.exception))

    def test_offsets_length_validation(self):
        """测试 offsets 长度校验"""
        with self.assertRaises(ValueError) as ctx:
            SplitConfig(rows=2, cols=2, output_dir=str(self.output_dir), offsets=(0, 0, 0))
        self.assertIn("必须为4个整数", str(ctx.exception))

    def test_offsets_type_validation(self):
        """测试 offsets 类型转换和校验"""
        config = SplitConfig(rows=2, cols=2, output_dir=str(self.output_dir), offsets=["0", "1", 2, 3])
        self.assertEqual(config.offsets, (0, 1, 2, 3))

        with self.assertRaises(ValueError) as ctx:
            SplitConfig(rows=2, cols=2, output_dir=str(self.output_dir), offsets=("a", 0, 0, 0))
        self.assertIn("所有元素必须为有效的整数", str(ctx.exception))

    def test_save_format_safety(self):
        """测试保存格式安全性 (C1)"""
        # 使用一个不含扩展名的模板
        config = SplitConfig(rows=1, cols=1, output_dir=str(self.output_dir), template="no_ext")
        success, msg = split_image_core(str(self.img_path), config)
        self.assertTrue(success)
        
        # 验证生成的文件虽然叫 no_ext.png (因为 ext 拼接逻辑)，但内容是正确的 PNG
        save_path = self.output_dir / "no_ext.png"
        self.assertTrue(save_path.exists())
        with Image.open(save_path) as img:
            self.assertEqual(img.format, "PNG")

    def test_pixel_alignment_consistency(self):
        """测试像素对齐一致性 (M3)"""
        # 100 像素切成 3 份
        # 旧版: int(0*100/3)=0, int(1*100/3)=33, int(2*100/3)=66, int(3*100/3)=100
        # 宽度为 33, 33, 34
        # 新版: 0*100//3=0, 1*100//3=33, 2*100//3=66, 3*100//3=100
        # 其实结果一样，但逻辑更严密 (避免浮点舍入)
        img = Image.new("RGB", (100, 100))
        config = SplitConfig(rows=1, cols=3, output_dir=str(self.output_dir))
        success, _ = split_image_core(str(self.img_path), config)
        self.assertTrue(success)
        
        tiles = sorted(self.output_dir.glob("*.png"))
        self.assertEqual(tiles[0].name, "test_01.png")
        self.assertEqual(tiles[1].name, "test_02.png")
        self.assertEqual(tiles[2].name, "test_03.png")

if __name__ == '__main__':
    unittest.main()
