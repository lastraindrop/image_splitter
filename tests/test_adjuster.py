# image_splitter/tests/test_adjuster.py
import unittest
import os
import tempfile
from PIL import Image
from pathlib import Path
from image_splitter.models import AdjustConfig
from image_splitter.core import process_image

class TestCanvasAdjuster(unittest.TestCase):
    def setUp(self):
        self._temp_dir_obj = tempfile.TemporaryDirectory()
        self.test_dir = Path(self._temp_dir_obj.name).resolve()
        self.output_dir = self.test_dir / "output"
        self.output_dir.mkdir(exist_ok=True)
        
        # 创建一个 100x100 的红色测试图
        self.img_path = self.test_dir / "test_100.png"
        Image.new("RGB", (100, 100), color="red").save(self.img_path)

    def tearDown(self):
        self._temp_dir_obj.cleanup()

    def test_canvas_padding(self):
        """测试画布扩充 (Padding)"""
        # 100x100 -> 200x200, 蓝色背景, 居中
        config = AdjustConfig(
            width=200, height=200, 
            bg_color=(0, 0, 255), 
            output_dir=str(self.output_dir)
        )
        success, _ = process_image(str(self.img_path), "canvas_adjuster", config)
        self.assertTrue(success)
        
        save_path = self.output_dir / "test_100_adjusted.png"
        with Image.open(save_path) as img:
            self.assertEqual(img.size, (200, 200))
            # 验证背景色 (边缘像素应该是蓝色)
            self.assertEqual(img.getpixel((0, 0)), (0, 0, 255))
            # 验证中心像素 (中心应该是红色)
            self.assertEqual(img.getpixel((100, 100)), (255, 0, 0))

    def test_canvas_cropping(self):
        """测试画布裁剪 (Cropping)"""
        # 100x100 -> 50x50, 从左上角截取
        config = AdjustConfig(
            width=50, height=50, 
            anchor="top-left",
            output_dir=str(self.output_dir)
        )
        success, _ = process_image(str(self.img_path), "canvas_adjuster", config)
        self.assertTrue(success)
        
        with Image.open(self.output_dir / "test_100_adjusted.png") as img:
            self.assertEqual(img.size, (50, 50))

    def test_canvas_ratio(self):
        """测试比例缩放画布"""
        # 100x100 -> 1.5倍宽, 0.5倍高 (150x50)
        config = AdjustConfig(
            width=1.5, height=0.5,
            output_dir=str(self.output_dir)
        )
        success, _ = process_image(str(self.img_path), "canvas_adjuster", config)
        self.assertTrue(success)
        
        with Image.open(self.output_dir / "test_100_adjusted.png") as img:
            self.assertEqual(img.size, (150, 50))

    def test_adjust_config_fail_fast(self):
        """无效配置应在模型层直接被拦截"""
        with self.assertRaises(ValueError):
            AdjustConfig(width=0, height=50, output_dir=str(self.output_dir))

if __name__ == '__main__':
    unittest.main()
