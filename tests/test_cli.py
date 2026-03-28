# tests/test_cli.py
import unittest
import os
import shutil
import sys
from pathlib import Path
from unittest.mock import patch
from cli import main

class TestImageSplitterCLI(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("test_cli_dynamic").resolve()
        self.output_dir = self.test_dir / "output"
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.test_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建测试图
        self.img_path = self.test_dir / "test.png"
        from PIL import Image
        Image.new("RGB", (100, 100), color="red").save(self.img_path)

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_cli_basic_flow(self):
        """测试 CLI 基础全流程运行"""
        test_args = [
            "cli.py", 
            str(self.img_path), 
            "-r", "2", 
            "-c", "2", 
            "-o", str(self.output_dir),
            "-j", "1" # 强制单进程方便测试
        ]
        
        with patch.object(sys, 'argv', test_args):
            with patch('sys.stdout'):
                exit_code = None
                try:
                    main()
                except SystemExit as e:
                    exit_code = e.code
                # main() 正常返回 (None) 或 sys.exit(0) 均视为成功
                self.assertIn(exit_code, (None, 0), msg=f"CLI 退出码异常: {exit_code}")
        
        # 验证结果
        self.assertTrue(self.output_dir.exists())
        files = list(self.output_dir.glob("*.png"))
        self.assertEqual(len(files), 4)

    def test_cli_recursive_discovery(self):
        """测试 CLI 递归目录搜索"""
        sub_dir = self.test_dir / "sub"
        sub_dir.mkdir()
        sub_img = sub_dir / "sub.jpg"
        from PIL import Image
        Image.new("RGB", (50, 50)).save(sub_img)
        
        test_args = [
            "cli.py", 
            str(self.test_dir), 
            "-r", "1", 
            "-c", "1", 
            "-o", str(self.output_dir),
            "--recursive"
        ]
        
        with patch.object(sys, 'argv', test_args):
            with patch('sys.stdout'):
                exit_code = None
                try:
                    main()
                except SystemExit as e:
                    exit_code = e.code
                self.assertIn(exit_code, (None, 0), msg=f"CLI 退出码异常: {exit_code}")
        
        # 应该发现 2 张图（顶层和子目录）
        # 1x1 切割，所以生成 2 张
        files = list(self.output_dir.glob("*"))
        self.assertEqual(len(files), 2)

    def test_cli_no_valid_files(self):
        """当输入路径无有效图片时，应 sys.exit(1)"""
        test_args = ["cli.py", str(self.test_dir / "nonexistent"), "-r", "2", "-c", "2"]
        
        with patch.object(sys, 'argv', test_args):
            with patch('sys.stdout'):
                with self.assertRaises(SystemExit) as ctx:
                    main()
                self.assertEqual(ctx.exception.code, 1)

    def test_glob_excludes_directories(self):
        """确保通配符不会错误匹配到同名目录"""
        fake_dir = self.test_dir / "trap.jpg"  # 名为 .jpg 的目录
        fake_dir.mkdir()
        
        test_args = [
            "cli.py", str(self.test_dir / "*.jpg"),
            "-r", "1", "-c", "1",
            "-o", str(self.output_dir)
        ]
        
        with patch.object(sys, 'argv', test_args):
            with patch('sys.stdout'):
                with self.assertRaises(SystemExit) as ctx:
                    main()
                # 没有有效文件，应退出 1
                self.assertEqual(ctx.exception.code, 1)

if __name__ == '__main__':
    unittest.main()
