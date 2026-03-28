# tests/test_core.py
import unittest
import os
import shutil
from PIL import Image
from pathlib import Path
from core import split_image_core, batch_process_images

class TestImageSplitter(unittest.TestCase):
    def setUp(self):
        # 动态创建测试环境，避免硬编码路径
        self.test_dir = Path("test_run_dynamic").resolve()
        self.output_dir = self.test_dir / "output"
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 准备测试素材字典 {名称: (路径, 宽高, 模式)}
        self.test_images = {
            "rgb": (self.test_dir / "test_rgb.png", (200, 200), "RGB"),
            "rgba": (self.test_dir / "test_rgba.png", (150, 200), "RGBA"),
            "small": (self.test_dir / "test_small.jpg", (10, 10), "RGB")
        }
        
        for name, (path, size, mode) in self.test_images.items():
            Image.new(mode, size, color='blue').save(path)

    def tearDown(self):
        # 彻底清理环境
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def _verify_split(self, success, msg, expected_success, expected_files_count=None, check_func=None):
        """统一的断言与结果检查辅助函数"""
        self.assertEqual(success, expected_success, msg=f"期望结果为 {expected_success}，但得到了 {success}。错误信息: {msg}")
        
        if expected_success and expected_files_count is not None:
            self.assertTrue(self.output_dir.exists())
            files = list(self.output_dir.glob("*"))
            self.assertEqual(len(files), expected_files_count, msg=f"生成文件数不符。期望: {expected_files_count}, 实际: {len(files)}")
            
            if check_func and files:
                with Image.open(files[0]) as img:
                    check_func(img)
                    
        # 重置输出目录以便并行子测试
        if self.output_dir.exists():
            for f in self.output_dir.glob("*"):
                if f.is_file(): f.unlink()

    def test_split_combinations(self):
        """1. 适应多种参数组合 (成功路径)"""
        rgb_path = self.test_images["rgb"][0]
        rgba_path = self.test_images["rgba"][0]

        test_cases = [
            # (path, rows, cols, offsets, template, expected_count, check_func)
            (rgb_path, 2, 2, (0,0,0,0), "{filename}_{index}", 4, None), 
            (str(rgb_path), 1, 3, (0,0,0,0), "{filename}_{index}", 3, None), # 测试字符串路径输入
            (rgba_path, 2, 2, (0,0,0,0), "{filename}_{index}", 4, lambda img: self.assertEqual(img.mode, 'RGBA')),
            (rgb_path, 2, 2, (10,10,10,10), "{filename}_{index}", 4, lambda img: self.assertEqual(img.size, (90, 90))), 
            (rgb_path, 1, 2, (0,0,0,0), "custom_{row}_{col}_{index}", 2, lambda img: self.assertTrue(any("custom_" in f.name for f in self.output_dir.glob("*")))),
        ]

        for path, r, c, offsets, template, count, check_func in test_cases:
            with self.subTest(path=Path(path).name, r=r, c=c):
                success, msg = split_image_core(str(path), r, c, str(self.output_dir), template=template, offsets=offsets)
                self._verify_split(success, msg, True, count, check_func)

    def test_split_edge_cases(self):
        """2. 测试异常逻辑"""
        rgb_path = self.test_images["rgb"][0]
        missing_path = self.test_dir / "missing.png"

        test_cases = [
            (rgb_path, 0, 2, (0,0,0,0), "{filename}_{index}", "大于0"), 
            (rgb_path, 2, 2, (150,0,150,0), "{filename}_{index}", "导致区域无效"),
            (rgb_path, 1, 2, (0,0,0,0), "bad_{invalid_key}", "无效的占位符"),
            (missing_path, 2, 2, (0,0,0,0), "{filename}_{index}", "找不到文件"),
        ]

        for path, r, c, offsets, template, err_keyword in test_cases:
            with self.subTest(err=err_keyword):
                success, msg = split_image_core(str(path), r, c, str(self.output_dir), template=template, offsets=offsets)
                self._verify_split(success, msg, False)
                self.assertIn(err_keyword, msg)

    def test_batch_process_e2e(self):
        """3. 全流程生成器测试"""
        input_paths = [str(v[0]) for v in self.test_images.values()]
        
        results = []
        for path, success, msg in batch_process_images(
            input_paths, rows=2, cols=2, output_root=str(self.output_dir), 
            template="bt_{filename}_{index}", offsets=(5, 5, 5, 5)
        ):
            results.append((path, success))
            
        self.assertEqual(len(results), 3)
        self.assertTrue(results[0][1]) # rgb
        self.assertTrue(results[1][1]) # rgba
        self.assertFalse(results[2][1]) # small (too small for offsets)

    def test_invalid_params_no_side_effects(self):
        """验证非法参数不会创建输出目录或产生文件"""
        clean_dir = self.test_dir / "should_not_exist"
        rgb_path = self.test_images["rgb"][0]
        
        # rows=0 应直接返回，不创建目录
        success, msg = split_image_core(str(rgb_path), 0, 2, str(clean_dir))
        self.assertFalse(success)
        self.assertFalse(clean_dir.exists(), "非法参数不应创建输出目录")

    def test_pixel_accuracy(self):
        """验证切割后子图像素与原图完全一致"""
        # 创建一张含有渐变色的测试图
        img = Image.new("RGB", (100, 100))
        for x in range(100):
            for y in range(100):
                img.putpixel((x, y), (x * 2, y * 2, 128))
        test_path = self.test_dir / "gradient.png"
        img.save(test_path)
        
        success, _ = split_image_core(str(test_path), 2, 2, str(self.output_dir))
        self.assertTrue(success)
        
        # 读取左上角子图，验证像素
        tiles = sorted(self.output_dir.glob("*.png"))
        with Image.open(tiles[0]) as tile:
            # 第一张 tile (0,0) 位置像素应等于原图 (0,0)
            self.assertEqual(tile.getpixel((0, 0)), (0, 0, 128))
            # tile 尺寸应该是 50x50，(49,49) 对应原图 (49,49)
            self.assertEqual(tile.getpixel((49, 49)), (98, 98, 128))

    def test_large_grid_completes(self):
        """验证 20x20=400 块切割正常完成"""
        img = Image.new("RGB", (400, 400), color="green")
        path = self.test_dir / "large.png"
        img.save(path)
        
        success, msg = split_image_core(str(path), 20, 20, str(self.output_dir))
        self.assertTrue(success)
        files = list(self.output_dir.glob("*"))
        self.assertEqual(len(files), 400)

if __name__ == '__main__':
    unittest.main()