import unittest
import tempfile
from pathlib import Path
from PIL import Image

try:
    import tkinter as tk
    from image_splitter import gui
except ImportError:
    tk = None

from image_splitter.core import register_all_processors
from image_splitter.engine.registry import ProcessorRegistry

class MockTkVar:
    def __init__(self, value):
        self._value = value
    def get(self):
        return self._value

@unittest.skipIf(tk is None, "Tkinter is not available")
class TestUIPreview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        register_all_processors()

    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("Tk environment unavailable")
        self.root.withdraw()
        self.canvas = tk.Canvas(self.root)
        self.theme = gui.UITheme()

    def tearDown(self):
        if hasattr(self, "root"):
            self.root.destroy()

    def test_all_processors_draw_preview(self):
        """确保所有处理器的 draw_preview 在收到合法的 mock 参数时不会抛出异常"""
        processors = ProcessorRegistry.list_all()
        for p in processors:
            with self.subTest(processor=p.name):
                # 构造 mock 的 dynamic_vars
                ui_meta = p.get_ui_metadata()
                mock_props = {}
                for m in ui_meta:
                    # 使用我们自定义的 MockTkVar 模拟 Tkinter 的 StringVar/IntVar 等
                    mock_props[m["name"]] = MockTkVar(m["default"])
                
                # 调用 draw_preview，预期不抛出异常
                try:
                    p.draw_preview(
                        canvas=self.canvas,
                        thumb_size=(100, 100),
                        canvas_pos=(10, 10),
                        ratio=1.0,
                        props=mock_props,
                        theme=self.theme
                    )
                except Exception as e:
                    self.fail(f"处理器 {p.name} 的 draw_preview 抛出异常: {e}")

    def test_draw_preview_graceful_failure(self):
        """测试遇到脏数据（例如字符串无法被解析为列表）时，draw_preview 应静默捕获，不破坏 GUI 线程"""
        p = ProcessorRegistry.get("custom_splitter")
        
        mock_props = {
            "h_lines": MockTkVar("NOT_A_LIST"),
            "v_lines": MockTkVar("NOT_A_LIST")
        }
        
        # 这个调用内部会通过 try-except 忽略异常
        try:
            p.draw_preview(
                canvas=self.canvas,
                thumb_size=(100, 100),
                canvas_pos=(0, 0),
                ratio=1.0,
                props=mock_props,
                theme=self.theme
            )
        except Exception as e:
            self.fail(f"draw_preview 没有正确捕获无效输入的异常: {e}")

if __name__ == '__main__':
    unittest.main()
