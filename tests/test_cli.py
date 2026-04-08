# tests/test_cli.py
import unittest
import os
import tempfile
import shutil
import sys
from pathlib import Path
from unittest.mock import patch
from image_splitter.cli import main

class TestImageSplitterCLI(unittest.TestCase):
    def setUp(self):
        self._temp_dir_obj = tempfile.TemporaryDirectory()
        self.test_dir = Path(self._temp_dir_obj.name).resolve()
        self.output_dir = self.test_dir / "output"
        # 注意：此处故意不提前创建 output_dir，以测试 CLI 的自动创建能力
        
        # 创建测试图
        self.img_path = self.test_dir / "test.png"
        from PIL import Image
        Image.new("RGB", (100, 100), color="red").save(self.img_path)

    def tearDown(self):
        self._temp_dir_obj.cleanup()

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

    def test_cli_output_dir_exclusion_logic(self):
        """验证 CLI 正确排除输出目录内的文件，且不受字符串前缀干扰"""
        # 创建一个名为 output_backup 的目录，它具有 output 的前缀，但不应被排除
        backup_dir = self.test_dir / "output_backup"
        backup_dir.mkdir()
        backup_img = backup_dir / "keep_me.png"
        from PIL import Image
        Image.new("RGB", (10, 10)).save(backup_img)
        
        # 此时 output_dir 即使还没创建，Path(args.output).resolve() 也会生效
        self.output_dir.mkdir(exist_ok=True)
        
        test_args = [
            "cli.py", str(backup_dir / "*.png"),
            "-r", "1", "-c", "1",
            "-o", str(self.output_dir)
        ]
        
        with patch.object(sys, 'argv', test_args):
            with patch('sys.stdout'):
                try:
                    main()
                except SystemExit as e:
                    self.assertEqual(e.code, 0)
                    
        # 验证 keep_me.png 被成功处理并输出到了 output_dir (1x1 切割，模板默认 {filename}_{index})
        self.assertTrue((self.output_dir / "keep_me_01.png").exists())

    def test_cli_high_concurrency(self):
        """测试高并发下的稳定性"""
        test_args = [
            "cli.py", str(self.img_path),
            "-r", "1", "-c", "1",
            "-o", str(self.output_dir),
            "-j", "8"
        ]
        with patch.object(sys, 'argv', test_args):
            with patch('sys.stdout'):
                try:
                    main()
                except SystemExit as e:
                    self.assertEqual(e.code, 0)
        self.assertTrue((self.output_dir / "test_01.png").exists())

    def test_cli_invalid_arguments(self):
        """测试非法参数类型（如 rows 传入字符串）"""
        test_args = ["cli.py", str(self.img_path), "-r", "abc", "-c", "2"]
        # argparse 会直接打印错误并退出
        with patch.object(sys, 'argv', test_args):
            with patch('sys.stderr'):
                with self.assertRaises(SystemExit):
                    main()

    def test_cli_rejects_zero_jobs(self):
        """并发数必须大于 0，避免在执行器层抛出运行时异常"""
        test_args = ["cli.py", str(self.img_path), "-r", "1", "-c", "1", "-j", "0"]
        with patch.object(sys, 'argv', test_args):
            with patch('sys.stderr'):
                with self.assertRaises(SystemExit):
                    main()

    def test_cli_auto_create_output_dir(self):
        """验证 CLI 会自动创建不存在的输出目录"""
        new_dir = self.test_dir / "brand_new_dir"
        self.assertFalse(new_dir.exists())
        
        test_args = [
            "cli.py", str(self.img_path),
            "-r", "1", "-c", "1",
            "-o", str(new_dir)
        ]
        with patch.object(sys, 'argv', test_args):
            with patch('sys.stdout'):
                main()
        
        self.assertTrue(new_dir.exists())
        self.assertTrue((new_dir / "test_01.png").exists())

    def test_cli_generic_processor_mode(self):
        """通用模式：通过 --processor 和 --set 调用任意处理器"""
        test_args = [
            "cli.py", str(self.img_path),
            "--processor", "format_converter",
            "--set", "format=JPEG",
            "--set", "quality=90",
            "-o", str(self.output_dir),
            "-j", "1"
        ]
        with patch.object(sys, 'argv', test_args):
            with patch('sys.stdout'):
                exit_code = None
                try:
                    main()
                except SystemExit as e:
                    exit_code = e.code
                self.assertIn(exit_code, (None, 0), msg=f"CLI 退出码异常: {exit_code}")

        self.assertTrue((self.output_dir / "test_01.jpg").exists())

    def test_cli_processor_not_found(self):
        """未知处理器应明确失败并返回退出码 1"""
        test_args = [
            "cli.py", str(self.img_path),
            "--processor", "not_exists_processor",
            "-o", str(self.output_dir)
        ]
        with patch.object(sys, 'argv', test_args):
            with patch('sys.stdout'):
                with self.assertRaises(SystemExit) as ctx:
                    main()
                self.assertEqual(ctx.exception.code, 1)

if __name__ == '__main__':
    unittest.main()
