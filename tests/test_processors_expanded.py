# image_splitter/tests/test_processors_expanded.py
import unittest
import os
import tempfile
from PIL import Image
from pathlib import Path
from image_splitter.core import process_image, register_all_processors
from image_splitter.models import SplitConfig

class TestProcessorsDeepDive(unittest.TestCase):
    """
    针对各处理器的深度参数适配与逻辑分析 (规则 3)
    """
    
    @classmethod
    def setUpClass(cls):
        # 确保所有插件已加载
        register_all_processors()

    def setUp(self):
        self._temp_dir_obj = tempfile.TemporaryDirectory()
        self.test_dir = Path(self._temp_dir_obj.name).resolve()
        self.output_dir = self.test_dir / "output"
        self.output_dir.mkdir(exist_ok=True)
        
        # 创建 100x100 半透明测试图
        self.rgba_path = self.test_dir / "test_rgba.png"
        Image.new("RGBA", (100, 100), color=(255, 0, 0, 100)).save(self.rgba_path)

    def tearDown(self):
        self._temp_dir_obj.cleanup()

    def test_grid_splitter_rounding_consistency(self):
        """规则 3: 边界点分析 - 100像素除以3的四舍五入一致性 (M3)"""
        config = SplitConfig(rows=1, cols=3, output_dir=str(self.output_dir))
        success, _ = process_image(str(self.rgba_path), "grid_splitter", config)
        self.assertTrue(success)
        
        tiles = sorted(self.output_dir.glob("*.png"))
        self.assertEqual(len(tiles), 3)
        
        # 验证总宽度是否维持不变 (原图 100)
        total_w = 0
        for t in tiles:
            with Image.open(t) as img:
                total_w += img.width
        self.assertEqual(total_w, 100, f"网格切割造成像素丢失或溢出: {total_w} != 100")

    def test_watermark_positioning_and_opacity(self):
        """规则 3: 适配情况 - 水印各象限定位与透明度叠加"""
        anchors = ["TL", "TR", "BL", "BR", "C"]
        for anchor in anchors:
            with self.subTest(anchor=anchor):
                config = {
                    "text": f"WD_{anchor}",
                    "opacity": 200,
                    "anchor": anchor,
                    "output_dir": str(self.output_dir),
                    "template": "{filename}_{anchor}"
                }
                success, msg = process_image(str(self.rgba_path), "text_watermark", config)
                self.assertTrue(success, f"水印处理失败 [Anchor: {anchor}]: {msg}")
                
                # 验证生成的文件能够被加载 (模板中指定了后缀或让 process_image 自动添加)
                try:
                    out_file = next(self.output_dir.glob(f"*_{anchor}.png"))
                except StopIteration:
                    self.fail(f"未找到水印测试输出文件: *_{anchor}.png, 提示: {msg}, 目录内容: {list(self.output_dir.glob('*'))}")
                
                with Image.open(out_file) as img:
                    self.assertEqual(img.mode, "RGBA", "水印叠加应保持 Alpha 通道")

    def test_color_adjuster_scaling(self):
        """规则 3: 运行流程 - 极端参数组合分析"""
        # 测试 2倍对比度 + 0倍亮度 (全黑)
        config = {
            "contrast": 2.0,
            "brightness": 0.0,
            "sharpness": 1.0,
            "color": 1.0,
            "output_dir": str(self.output_dir),
            "template": "{filename}_color_tuned"
        }
        success, msg = process_image(str(self.rgba_path), "color_adjuster", config)
        self.assertTrue(success, f"色彩调节测试失败: {msg}")
        
        try:
            out_file = next(self.output_dir.glob("*_color_tuned.png"))
        except StopIteration:
            self.fail(f"未找到色彩调节输出文件: {msg}, 目录内容: {list(self.output_dir.glob('*'))}")
            
        with Image.open(out_file) as img:
            pixels = list(img.convert("RGB").getdata())
            is_all_black = all(p == (0, 0, 0) for p in pixels)
            self.assertTrue(is_all_black, f"参数适配错误：亮度 0 应当产出全黑图像")

    def test_format_converter_flattens_alpha_for_jpeg(self):
        """带透明通道的图像导出为 JPEG 时应自动铺底，避免保存失败"""
        config = {
            "format": "JPEG",
            "quality": 90,
            "output_dir": str(self.output_dir),
            "template": "alpha_to_jpeg"
        }
        success, msg = process_image(str(self.rgba_path), "format_converter", config)
        self.assertTrue(success, msg)

        out_file = self.output_dir / "alpha_to_jpeg.jpg"
        self.assertTrue(out_file.exists())
        with Image.open(out_file) as img:
            self.assertEqual(img.mode, "RGB")

    def test_canvas_adjuster_mixed_inputs(self):
        """规则 3: 参数组合 - float (比例) 与 int (绝对像素) 的适配"""
        test_cases = [
            {"width": 150, "height": 150, "anchor": "center", "expected_size": (150, 150)}, # 绝对像素
            {"width": 2.0, "height": 0.5, "anchor": "top-left", "expected_size": (200, 50)}, # 比例
        ]
        
        for case in test_cases:
            with self.subTest(case=case):
                # 清空输出
                for f in self.output_dir.glob("*"): f.unlink()
                
                success, msg = process_image(str(self.rgba_path), "canvas_adjuster", {**case, "output_dir": str(self.output_dir), "template": "{filename}_adjusted"})
                self.assertTrue(success, f"画布调整测试失败 [Case: {case}]: {msg}")
                
                try:
                    out_file = next(self.output_dir.glob("*_adjusted.png"))
                except StopIteration:
                    self.fail(f"未找到画布调整输出文件: {msg}, 目录内容: {list(self.output_dir.glob('*'))}")
                
                with Image.open(out_file) as img:
                    self.assertEqual(img.size, case["expected_size"])

    def test_large_grid_completes(self):
        """规则 3: 运行完整流程 - 400块大规模切分压力测试"""
        img = Image.new("RGB", (400, 400), color="green")
        path = self.test_dir / "large.png"
        img.save(path)
        
        config = SplitConfig(rows=20, cols=20, output_dir=str(self.output_dir))
        success, msg = process_image(str(path), "grid_splitter", config)
        self.assertTrue(success)
        files = list(self.output_dir.glob("*"))
        self.assertEqual(len(files), 400)

    def test_pixel_accuracy(self):
        """规则 3: 关键点分析 - 验证处理后子图像素与原图完全一致"""
        img = Image.new("RGB", (100, 100))
        for x in range(100):
            for y in range(100):
                img.putpixel((x, y), (x * 2, y * 2, 128))
        test_path = self.test_dir / "gradient.png"
        img.save(test_path)
        
        config = SplitConfig(rows=2, cols=2, output_dir=str(self.output_dir))
        success, _ = process_image(str(test_path), "grid_splitter", config)
        self.assertTrue(success)
        
        tiles = sorted(self.output_dir.glob("*.png"))
        with Image.open(tiles[0]) as tile:
            self.assertEqual(tile.getpixel((0, 0)), (0, 0, 128))
            self.assertEqual(tile.getpixel((49, 49)), (98, 98, 128))

    def test_zero_pixel_avoidance(self):
        """规则 3: 处理极限情况 - 偏移量导致区域极小时的容错"""
        # 原图 100x100, 偏移 (48, 48, 48, 48) -> 剩 4x4
        # 切 5x5 -> 必会有 0px 情况
        config = SplitConfig(rows=5, cols=5, output_dir=str(self.output_dir), offsets=(48, 48, 48, 48))
        success, msg = process_image(str(self.rgba_path), "grid_splitter", config)
        self.assertTrue(success, f"处理极小区域不应报错: {msg}")
        files = list(self.output_dir.glob("*"))
        self.assertGreater(len(files), 0)

if __name__ == '__main__':
    unittest.main()
