import unittest
import os
import shutil
from PIL import Image
from core import split_image_core

class TestImageSplitter(unittest.TestCase):
    def setUp(self):
        # 创建测试环境
        self.test_dir = "test_run"
        self.output_dir = os.path.join(self.test_dir, "output")
        if not os.path.exists(self.test_dir):
            os.makedirs(self.test_dir)
        
        # 创建一张 200x200 的测试图片
        self.img_path = os.path.join(self.test_dir, "test.png")
        Image.new('RGB', (200, 200), color='red').save(self.img_path)

    def tearDown(self):
        # 清理测试环境
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_basic_split(self):
        # 测试 2x2 切割
        success, msg = split_image_core(self.img_path, 2, 2, self.output_dir)
        self.assertTrue(success)
        self.assertTrue(os.path.exists(self.output_dir))
        files = os.listdir(self.output_dir)
        self.assertEqual(len(files), 4)

    def test_offset_split(self):
        # 测试带有偏移量的切割 (左上右下各10像素，有效区域变为 180x180)
        offsets = (10, 10, 10, 10)
        success, msg = split_image_core(self.img_path, 2, 2, self.output_dir, offsets=offsets)
        self.assertTrue(success)
        # 验证其中一个切片的大小应该是 90x90
        files = os.listdir(self.output_dir)
        sample_path = os.path.join(self.output_dir, files[0])
        with Image.open(sample_path) as img:
            self.assertEqual(img.size, (90, 90))

    def test_template_naming(self):
        # 测试自定义模板
        template = "custom_{row}_{col}_{index}"
        success, msg = split_image_core(self.img_path, 1, 2, self.output_dir, template=template)
        self.assertTrue(success)
        files = sorted(os.listdir(self.output_dir))
        self.assertIn("custom_1_1_01.png", files)
        self.assertIn("custom_1_2_02.png", files)

    def test_invalid_params(self):
        # 测试非法参数
        success, msg = split_image_core(self.img_path, 0, 2, self.output_dir)
        self.assertFalse(success)
        self.assertIn("必须大于0", msg)

    def test_excessive_offset(self):
        # 测试过大的偏移量
        offsets = (150, 0, 150, 0) # 150+150 > 200
        success, msg = split_image_core(self.img_path, 2, 2, self.output_dir, offsets=offsets)
        self.assertFalse(success)
        self.assertIn("偏移量过大", msg)

if __name__ == '__main__':
    unittest.main()
