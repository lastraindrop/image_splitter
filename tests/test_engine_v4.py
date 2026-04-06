# image_splitter/tests/test_engine_v4.py
import unittest
import os
import tempfile
from PIL import Image
from pathlib import Path
from image_splitter.core import process_image, register_all_processors
from image_splitter.engine.registry import ProcessorRegistry
from image_splitter.models import SplitConfig, AdjustConfig

class TestEngineFramework(unittest.TestCase):
    """
    规则 1: 始终适应最新的插件架构体系
    规则 3: 验证架构是否正确运行
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
        
        # 创建一个复杂的测试图 (100x100) 以便质量参数能产生体积差异
        img = Image.new("RGB", (100, 100))
        # 加入一些噪点
        for x in range(100):
            for y in range(100):
                img.putpixel((x, y), (x % 255, y % 255, (x+y) % 255))
        self.img_path = self.test_dir / "base_test.png"
        img.save(self.img_path)

    def tearDown(self):
        self._temp_dir_obj.cleanup()

    def test_registry_integrity(self):
        """架构检查：所有处理器是否都遵循 V4.0 标准协议"""
        processors = ProcessorRegistry.list_all()
        self.assertGreater(len(processors), 0, "注册表不应为空")
        
        required_attrs = ["name", "display_name", "category", "process", "draw_preview", "get_ui_metadata"]
        for p in processors:
            with self.subTest(processor=p.name):
                for attr in required_attrs:
                    self.assertTrue(hasattr(p, attr), f"处理器 {p.name} 缺少核心接口: {attr}")

    def test_processor_generic_smoke(self):
        """参数适配检查：所有处理器是否能接受基础 dict 调用而不崩溃"""
        processors = ProcessorRegistry.list_all()
        for p in processors:
            with self.subTest(processor=p.name):
                # 构造最简有效配置
                ui_meta = p.get_ui_metadata()
                mock_config = {m["name"]: m["default"] for m in ui_meta}
                mock_config["output_dir"] = str(self.output_dir)
                
                # 运行处理
                success, msg = process_image(str(self.img_path), p.name, mock_config)
                self.assertTrue(success, f"处理器 {p.name} 在默认配置下运行失败: {msg}")
                
                # 验证是否有文件生成
                generated = list(self.output_dir.glob("*"))
                self.assertGreater(len(generated), 0, f"处理器 {p.name} 未生成任何文件")
                
                # 清理以便下一个子测试
                for f in generated: f.unlink()

    def test_path_security_regression(self):
        """规则 3: 关键点 - 路径穿越与模板安全性"""
        malicious_template = "../shady_{filename}_{index}"
        config = SplitConfig(rows=1, cols=1, output_dir=str(self.output_dir), template=malicious_template)
        
        success, msg = process_image(str(self.img_path), "grid_splitter", config)
        self.assertTrue(success)
        
        # 验证文件是否被“强制”留在 output_dir 内
        expected_name = f"shady_{self.img_path.stem}_01.png"
        evil_path = self.output_dir.parent / expected_name
        safe_path = self.output_dir / expected_name
        
        self.assertFalse(evil_path.exists(), "安全漏洞：文件成功逃逸出输出目录！")
        self.assertTrue(safe_path.exists(), "文件应在安全目录下生成")

    def test_save_format_parameter_adaptation(self):
        """规则 3: 参数组合适配 - 验证质量参数在不同格式间的传递情况"""
        # 测试 WebP 高压缩率
        config = {
            "format": "WebP",
            "quality": 10,
            "output_dir": str(self.output_dir),
            "template": "low_q"
        }
        success, _ = process_image(str(self.img_path), "format_converter", config)
        self.assertTrue(success)
        
        generated_low = self.output_dir / "low_q.webp"
        self.assertTrue(generated_low.exists())
        low_q_size = generated_low.stat().st_size
        
        # 测试 WebP 高质量
        config["quality"] = 100
        config["template"] = "high_q"
        process_image(str(self.img_path), "format_converter", config)
        generated_high = self.output_dir / "high_q.webp"
        self.assertTrue(generated_high.exists())
        high_q_size = generated_high.stat().st_size
        
        # 质量参数应当显著影响文件大小 (考虑到 WebP 头部开销，对比 10 和 100)
        self.assertGreater(high_q_size, low_q_size, f"质量参数未生效: {high_q_size} <= {low_q_size}")

if __name__ == '__main__':
    unittest.main()
