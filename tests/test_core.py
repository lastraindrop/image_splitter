# tests/test_core.py
import unittest
import os
import tempfile
import shutil
from PIL import Image
from pathlib import Path
from core import split_image_core, batch_process_images
from models import SplitConfig

class TestImageSplitter(unittest.TestCase):
    def setUp(self):
        # 使用 tempfile 生成唯一的临时目录，确保环境隔离且无副作用
        self._temp_dir_obj = tempfile.TemporaryDirectory()
        self.test_dir = Path(self._temp_dir_obj.name).resolve()
        self.output_dir = self.test_dir / "output"
        self.output_dir.mkdir(exist_ok=True)
        
        # 准备测试素材字典 {名称: (路径, 宽高, mode, color)}
        self.test_images = {
            "rgb": (self.test_dir / "test_rgb.png", (200, 200), "RGB", (0,0,255)),
            "rgba": (self.test_dir / "test_rgba.png", (150, 200), "RGBA", (255,0,0,128)),
            "small": (self.test_dir / "test_small.jpg", (10, 10), "RGB", (255,255,255))
        }
        
        for name, (path, size, mode, color) in self.test_images.items():
            Image.new(mode, size, color=color).save(path)

    def tearDown(self):
        # 自动触发 TemporaryDirectory 的清理逻辑
        self._temp_dir_obj.cleanup()

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
            # 完整占位符矩阵测试
            (rgb_path, 1, 2, (0,0,0,0), "p_{row}_{col}_{index}_{filename}", 2, 
             lambda img: self.assertTrue(all(p in f.name for p in ["p_1", "test_rgb"] for f in self.output_dir.glob("p*")))),
        ]

        for path, r, c, offsets, template, count, check_func in test_cases:
            with self.subTest(path=Path(path).name, r=r, c=c):
                config = SplitConfig(rows=r, cols=c, output_dir=str(self.output_dir), template=template, offsets=offsets)
                success, msg = split_image_core(str(path), config)
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
                try:
                    config = SplitConfig(rows=r, cols=c, output_dir=str(self.output_dir), template=template, offsets=offsets)
                    success, msg = split_image_core(str(path), config)
                except ValueError as e:
                    success, msg = False, str(e)
                
                self._verify_split(success, msg, False)
                self.assertIn(err_keyword, msg)

    def test_batch_process_e2e(self):
        """3. 全流程生成器测试"""
        input_paths = [str(v[0]) for v in self.test_images.values()]
        config = SplitConfig(rows=2, cols=2, output_dir=str(self.output_dir), template="bt_{filename}_{index}", offsets=(5, 5, 5, 5))
        
        results = []
        for path, success, msg in batch_process_images(input_paths, config):
            results.append((path, success))
            
        self.assertEqual(len(results), 3)
        self.assertTrue(results[0][1]) # rgb
        self.assertTrue(results[1][1]) # rgba
        self.assertFalse(results[2][1]) # small (too small for offsets)

    def test_invalid_params_no_side_effects(self):
        """验证非法参数不会创建输出目录或产生文件"""
        clean_dir = self.test_dir / "should_not_exist"
        rgb_path = self.test_images["rgb"][0]
        
        # rows=0 应触发 SplitConfig 的校验
        with self.assertRaises(ValueError) as ctx:
            SplitConfig(rows=0, cols=2, output_dir=str(clean_dir))
        self.assertIn("大于0", str(ctx.exception))
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
        
        config = SplitConfig(rows=2, cols=2, output_dir=str(self.output_dir))
        success, _ = split_image_core(str(test_path), config)
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
        
        config = SplitConfig(rows=20, cols=20, output_dir=str(self.output_dir))
        success, msg = split_image_core(str(path), config)
        self.assertTrue(success)
        files = list(self.output_dir.glob("*"))
        self.assertEqual(len(files), 400)

    def test_alpha_channel_preservation(self):
        """验证切割后子图像的 Alpha 通道（透明度）被正确保留"""
        rgba_path, size, mode, color = self.test_images["rgba"]
        config = SplitConfig(rows=1, cols=1, output_dir=str(self.output_dir))
        success, _ = split_image_core(str(rgba_path), config)
        self.assertTrue(success)
        
        # 检查生成的图片
        output_file = next(self.output_dir.glob("*.png"))
        with Image.open(output_file) as img:
            self.assertEqual(img.mode, "RGBA")
            # 验证透明度像素值 (128)
            alpha = img.getpixel((0, 0))[3]
            self.assertEqual(alpha, 128)

    def test_zero_pixel_avoidance(self):
        """验证核心逻辑能够优雅地跳过那些被偏移量完全‘切没’的空白单元格"""
        rgb_path = self.test_images["rgb"][0]
        # 设置极大偏移量，使有效裁剪区极小
        # 原图 200x200, 偏移 (95, 95, 95, 95) -> 剩 10x10
        # 如果 rows=20, 则每格只有 0.5px -> int 转换后可能出现 0
        config = SplitConfig(rows=20, cols=20, output_dir=str(self.output_dir), offsets=(95, 95, 95, 95))
        success, msg = split_image_core(str(rgb_path), config)
        self.assertTrue(success)
        # 实际生成的有效文件数应小于或等于原计划，且不应崩溃
        files = list(self.output_dir.glob("*"))
        self.assertGreater(len(files), 0)

    def test_path_traversal_prevention(self):
        """4. 验证恶意模板无法将文件写入输出目录之外"""
        rgb_path = self.test_images["rgb"][0]
        # 尝试通过模板注入路径穿越字符
        malicious_template = "../evil_{filename}_{index}"
        
        config = SplitConfig(rows=1, cols=1, output_dir=str(self.output_dir), template=malicious_template)
        success, msg = split_image_core(str(rgb_path), config)
        self.assertTrue(success)
        
        # 验证文件是否安全地在 output_dir 内部生成，而不是父目录
        expected_safe_name = f"evil_{rgb_path.stem}_01.png"
        safe_path = self.output_dir / expected_safe_name
        self.assertTrue(safe_path.exists(), "文件未生成在安全的输出目录内")
        
        # 验证父目录没有被污染
        evil_path = self.output_dir.parent / expected_safe_name
        self.assertFalse(evil_path.exists(), "发生路径穿越漏洞！")

    def test_split_config_validation(self):
        """5. 验证模型层的数据校验能力"""
        with self.assertRaises(ValueError) as ctx:
            SplitConfig(rows=-1, cols=2, output_dir="out")
        self.assertIn("必须大于0", str(ctx.exception))
        
        with self.assertRaises(ValueError) as ctx:
            SplitConfig(rows=2, cols=2, output_dir="out", offsets=(10, -5, 0, 0))
        self.assertIn("不能为负数", str(ctx.exception))

if __name__ == '__main__':
    unittest.main()