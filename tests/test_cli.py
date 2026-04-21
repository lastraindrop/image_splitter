# tests/test_cli.py
import unittest
import tempfile
import sys
from pathlib import Path
from unittest.mock import patch
from image_splitter.cli import main

class TestImageSplitterCLI(unittest.TestCase):
    def setUp(self):
        self._temp_dir_obj = tempfile.TemporaryDirectory()
        self.test_dir = Path(self._temp_dir_obj.name).resolve()
        self.output_dir = self.test_dir / "output"
        # Note: Intentionally do not create output_dir beforehand to test CLI's auto-creation capability
        
        # Create test image
        self.img_path = self.test_dir / "test.png"
        from PIL import Image
        Image.new("RGB", (100, 100), color="red").save(self.img_path)

    def tearDown(self):
        self._temp_dir_obj.cleanup()

    def test_cli_basic_flow(self):
        """Test basic full flow of CLI."""
        test_args = [
            "cli.py", 
            str(self.img_path), 
            "-r", "2", 
            "-c", "2", 
            "-o", str(self.output_dir),
            "-j", "1" # Force single process for easier testing
        ]
        
        with patch.object(sys, 'argv', test_args):
            with patch('sys.stdout'):
                exit_code = None
                try:
                    main()
                except SystemExit as e:
                    exit_code = e.code
                # main() returns None or sys.exit(0), both regarded as success
                self.assertIn(exit_code, (None, 0), msg=f"CLI exit code abnormal: {exit_code}")
        
        # Verify results
        self.assertTrue(self.output_dir.exists())
        files = list(self.output_dir.glob("*.png"))
        self.assertEqual(len(files), 4)

    def test_cli_recursive_discovery(self):
        """Test CLI recursive directory search."""
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
                self.assertIn(exit_code, (None, 0), msg=f"CLI exit code abnormal: {exit_code}")
        
        # Should find 2 images (top-level and sub-directory)
        # 1x1 split, so 2 generated
        files = list(self.output_dir.glob("*"))
        self.assertEqual(len(files), 2)

    def test_cli_no_valid_files(self):
        """When input path has no valid images, should sys.exit(1)."""
        test_args = ["cli.py", str(self.test_dir / "nonexistent"), "-r", "2", "-c", "2"]
        
        with patch.object(sys, 'argv', test_args):
            with patch('sys.stdout'):
                with self.assertRaises(SystemExit) as ctx:
                    main()
                self.assertEqual(ctx.exception.code, 1)

    def test_glob_excludes_directories(self):
        """Ensure wildcards don't incorrectly match directories with same names."""
        fake_dir = self.test_dir / "trap.jpg"  # Directory named .jpg
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
                # No valid files, should exit 1
                self.assertEqual(ctx.exception.code, 1)

    def test_cli_output_dir_exclusion_logic(self):
        """Verify CLI correctly excludes files in the output directory, without string prefix interference."""
        # Create a directory named output_backup, which has 'output' prefix but should not be excluded
        backup_dir = self.test_dir / "output_backup"
        backup_dir.mkdir()
        backup_img = backup_dir / "keep_me.png"
        from PIL import Image
        Image.new("RGB", (10, 10)).save(backup_img)
        
        # Even if output_dir is not yet created, Path(args.output).resolve() works
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
                    
        # Verify keep_me.png was successfully processed and output to output_dir
        self.assertTrue((self.output_dir / "keep_me_01.png").exists())

    def test_cli_high_concurrency(self):
        """Test stability under high concurrency."""
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
        """Test invalid argument types (e.g., passing string for rows)."""
        test_args = ["cli.py", str(self.img_path), "-r", "abc", "-c", "2"]
        # argparse prints error and exits directly
        with patch.object(sys, 'argv', test_args):
            with patch('sys.stderr'):
                with self.assertRaises(SystemExit):
                    main()

    def test_cli_rejects_zero_jobs(self):
        """Concurrency must be greater than 0 to avoid runtime exceptions in executor layer."""
        test_args = ["cli.py", str(self.img_path), "-r", "1", "-c", "1", "-j", "0"]
        with patch.object(sys, 'argv', test_args):
            with patch('sys.stderr'):
                with self.assertRaises(SystemExit):
                    main()

    def test_cli_auto_create_output_dir(self):
        """Verify CLI automatically creates non-existent output directories."""
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
        """Generic mode: call any processor via --processor and --set."""
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
                self.assertIn(exit_code, (None, 0), msg=f"CLI exit code abnormal: {exit_code}")

        self.assertTrue((self.output_dir / "test_01.jpg").exists())

    def test_cli_processor_not_found(self):
        """Unknown processor should fail explicitly and return exit code 1."""
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
