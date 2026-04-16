# image_splitter/tests/test_dispatcher_coercion.py
import unittest
from PIL import Image
from image_splitter.engine.dispatcher import CommandDispatcher
from image_splitter.engine.registry import ProcessorRegistry
from image_splitter.core import register_all_processors

class TestDispatcherCoercion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        register_all_processors()

    def test_dispatcher_injects_defaults(self):
        """验证 Dispatcher 是否能为省略参数的操作符注入默认值"""
        img = Image.new("RGB", (100, 100))
        
        # grid_splitter() 不带参数，默认应为 3x3
        cmd = "grid_splitter()"
        results = CommandDispatcher.execute_chain(img, cmd)
        
        # 3x3 = 9 块
        self.assertEqual(len(results), 9)
        # 100 // 3 = 33
        self.assertEqual(results[0].width, 33)

    def test_dispatcher_coerces_types(self):
        """验证 Dispatcher 是否能将字符串参数正确转换为目标类型"""
        img = Image.new("RGB", (100, 100))
        
        # rows="2" (字符串) 应该被强制转换为 int
        cmd = "grid_splitter(rows='2', cols=2)"
        results = CommandDispatcher.execute_chain(img, cmd)
        
        self.assertEqual(len(results), 4)
        self.assertEqual(results[0].height, 50)

    def test_dispatcher_complex_chain(self):
        """测试复杂链式调用下的类型流转"""
        img = Image.new("RGB", (100, 100))
        
        # 先缩放为 0.5 (50x50)，再切成 2x2
        cmd = "resizer(width=0.5, height=0.5) | grid_splitter(rows=2, cols=2)"
        results = CommandDispatcher.execute_chain(img, cmd)
        
        self.assertEqual(len(results), 4)
        self.assertEqual(results[0].size, (25, 25))

if __name__ == '__main__':
    unittest.main()
