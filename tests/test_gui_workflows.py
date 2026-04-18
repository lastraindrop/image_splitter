import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from PIL import Image

try:
    import tkinter as tk
    from image_splitter import gui
except ImportError:
    tk = None

@unittest.skipIf(tk is None, "Tkinter is not available")
class TestGuiWorkflows(unittest.TestCase):
    def setUp(self):
        self._temp_dir_obj = tempfile.TemporaryDirectory()
        self.test_dir = Path(self._temp_dir_obj.name)
        self.output_dir = self.test_dir / "output"
        self.output_dir.mkdir(exist_ok=True)
        self.img_path = self.test_dir / "test_gui_image.png"
        Image.new("RGB", (100, 100), color="blue").save(self.img_path)

        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("Tk environment unavailable (e.g. headless CI)")
        self.root.withdraw()
        self.app = gui.ImageSplitterApp(self.root)

    def tearDown(self):
        if hasattr(self, "root"):
            self.root.destroy()
        self._temp_dir_obj.cleanup()

    def test_full_workflow_config_coercion_and_run(self):
        with patch.object(gui.filedialog, "askopenfilenames", return_value=[str(self.img_path)]):
            self.app.select_files()
            
        self.assertEqual(len(self.app.current_files), 1)
        self.assertEqual(self.app.current_orig_size, (100, 100))

        target_processor_name = "Format Converter"
        self.assertIn(target_processor_name, self.app.processor_combo["values"])
        
        self.app.active_processor_name.set(target_processor_name)
        self.app._on_processor_changed()
        
        # 验证工具提示是否已更新
        self.assertIn("Export", self.app.tool_tip_var.get())

        # 3. 模拟修改参数
        self.assertIn("format", self.app.dynamic_vars)
        self.assertIn("quality", self.app.dynamic_vars)
        self.app.dynamic_vars["format"].set("JPEG")
        self.app.dynamic_vars["quality"].set("95") # 字符串类型输入

        # 4. 模拟运行并拦截 threading.Thread 验证传给工作线程的参数
        with patch.object(gui.filedialog, "askdirectory", return_value=str(self.output_dir)):
            with patch('threading.Thread') as mock_thread:
                self.app.run_batch()
                
                mock_thread.assert_called_once()
                args, kwargs = mock_thread.call_args
                
                # target=self.work_thread, args=(p_name, processed_config, output_dir)
                thread_args = kwargs.get('args', args[1] if len(args) > 1 else None)
                self.assertIsNotNone(thread_args)
                
                p_name, processed_config, out_dir = thread_args
                self.assertEqual(p_name, "format_converter")
                self.assertEqual(out_dir, str(self.output_dir))
                
                # 验证 coercion 是否生效
                self.assertEqual(processed_config["format"], "JPEG")
                self.assertEqual(processed_config["quality"], 95) # 应该是整数，不是字符串
                self.assertIsInstance(processed_config["quality"], int)

if __name__ == '__main__':
    unittest.main()
