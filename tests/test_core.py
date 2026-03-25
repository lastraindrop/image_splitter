import unittest
import os
import shutil
from PIL import Image
from core import split_image_core, batch_process_images

class TestImageSplitter(unittest.TestCase):
    def setUp(self):
        # 动态创建测试环境，避免硬编码重复
        self.test_dir = "test_run_dynamic"
        self.output_dir = os.path.join(self.test_dir, "output")
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 准备测试素材字典 {名称: (路径, 宽高, 模式)}
        self.test_images = {
            "rgb": (os.path.join(self.test_dir, "test_rgb.png"), (200, 200), "RGB"),
            "rgba": (os.path.join(self.test_dir, "test_rgba.png"), (150, 200), "RGBA"),
            "small": (os.path.join(self.test_dir, "test_small.jpg"), (10, 10), "RGB")
        }
        
        for name, (path, size, mode) in self.test_images.items():
            Image.new(mode, size, color='blue').save(path)

    def tearDown(self):
        # 彻底清理环境
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def _verify_split(self, success, msg, expected_success, expected_files_count=None, check_func=None):
        """统一的断言与结果检查辅助函数，彻底消除重复的断言代码"""
        self.assertEqual(success, expected_success, msg=f"期望的成功状态为 {expected_success}，但实际为 {success}. 提示信息: {msg}")
        
        if expected_success and expected_files_count is not None:
            self.assertTrue(os.path.exists(self.output_dir))
            files = os.listdir(self.output_dir)
            self.assertEqual(len(files), expected_files_count, msg=f"生成文件数不符。期望: {expected_files_count}, 实际: {len(files)}")
            
            # 支持动态传入回调函数校验图片属性
            if check_func and files:
                sample_path = os.path.join(self.output_dir, files[0])
                with Image.open(sample_path) as img:
                    check_func(img)
                    
        # 无论成功与否，重置输出目录以备下一个子测试 (subTest)
        if os.path.exists(self.output_dir):
            shutil.rmtree(self.output_dir)
            os.makedirs(self.output_dir, exist_ok=True)

    def test_split_combinations(self):
        """1. 适应多种参数组合 (成功路径): 运用 subTest 参数化测试消灭雷同代码"""
        rgb_path = self.test_images["rgb"][0]
        rgba_path = self.test_images["rgba"][0]

        # 数据驱动：测试多种不同的切分参数情况
        test_cases = [
            # (image_path, rows, cols, offsets, template, expected_count, check_func)
            (rgb_path, 2, 2, (0,0,0,0), "{filename}_{index}", 4, None), # 基础 2x2
            (rgb_path, 1, 3, (0,0,0,0), "{filename}_{index}", 3, None), # 非正方形 (长宽不整除)
            (rgba_path, 2, 2, (0,0,0,0), "{filename}_{index}", 4, lambda img: self.assertEqual(img.mode, 'RGBA')), # RGBA 色彩模式保留
            (rgb_path, 2, 2, (10,10,10,10), "{filename}_{index}", 4, lambda img: self.assertEqual(img.size, (90, 90))), # 正常偏移量计算
            (rgb_path, 1, 2, (0,0,0,0), "custom_{row}_{col}_{index}", 2, lambda img: self.assertTrue(any(f.startswith("custom_") for f in os.listdir(self.output_dir)))), # 自定义合法模板
        ]

        for path, r, c, offsets, template, count, check_func in test_cases:
            with self.subTest(path=os.path.basename(path), r=r, c=c, offsets=offsets, template=template):
                success, msg = split_image_core(path, r, c, self.output_dir, template=template, offsets=offsets)
                self._verify_split(success, msg, True, count, check_func)

    def test_split_edge_cases(self):
        """2. 测试异常与边缘情况 (失败路径): 验证防御性代码是否有效"""
        rgb_path = self.test_images["rgb"][0]
        missing_path = os.path.join(self.test_dir, "missing.png")

        test_cases = [
            # (image_path, rows, cols, offsets, template, expected_err_keyword)
            (rgb_path, 0, 2, (0,0,0,0), "{filename}_{index}", "大于0"), # 无效行列
            (rgb_path, -1, -2, (0,0,0,0), "{filename}_{index}", "大于0"), # 负数边界
            (rgb_path, 2, 2, (150,0,150,0), "{filename}_{index}", "偏移量过大"), # 越界偏移
            (rgb_path, 1, 2, (0,0,0,0), "bad_{invalid_key}", "无效的占位符"), # 非法模板
            (missing_path, 2, 2, (0,0,0,0), "{filename}_{index}", "找不到文件"), # 文件不存在
        ]

        for path, r, c, offsets, template, err_keyword in test_cases:
            with self.subTest(desc=err_keyword, r=r, offsets=offsets):
                success, msg = split_image_core(path, r, c, self.output_dir, template=template, offsets=offsets)
                self._verify_split(success, msg, False)
                self.assertIn(err_keyword, msg)

    def test_batch_process_generator_e2e(self):
        """3. 端到端 E2E 测试: 覆盖最新的 Generator 批量处理架构"""
        input_paths = [
            self.test_images["rgb"][0],   # 200x200, 应该成功
            self.test_images["small"][0], # 10x10,   偏移量 20 会导致这张失败
            self.test_images["rgba"][0]   # 150x200, 应该成功
        ]
        
        results = []
        # 使用生成器进行全流程处理，故意使用一个会使 small 图片失败的偏移量 (20)
        for path, success, msg in batch_process_images(
            input_paths, rows=2, cols=2, output_root=self.output_dir, 
            template="batch_{filename}_{index}", offsets=(20, 20, 20, 20)
        ):
            results.append((path, success))
            
        # 确保遍历了所有文件
        self.assertEqual(len(results), 3)
        
        # 验证每个文件的处理状态
        self.assertEqual(results[0][1], True)  # rgb 成功
        self.assertEqual(results[1][1], False) # small 失败 (有效图片区域无效)
        self.assertEqual(results[2][1], True)  # rgba 成功
        
        # 验证最终生成的文件数量：rgb(4) + rgba(4) = 8 张
        files = os.listdir(self.output_dir)
        self.assertEqual(len(files), 8)

if __name__ == '__main__':
    unittest.main()