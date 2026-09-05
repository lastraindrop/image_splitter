"""Tests for CLI."""

import sys
import tempfile
import unittest
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

    def run_cli(self, test_args, *, stderr=False):
        """Run CLI main() with patched argv and captured output.

        Returns ``None`` when main returns normally, or the SystemExit code.
        """
        stream = 'sys.stderr' if stderr else 'sys.stdout'
        with patch.object(sys, 'argv', test_args):
            with patch(stream):
                try:
                    main()
                except SystemExit as e:
                    return e.code
        return None

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
        
        exit_code = self.run_cli(test_args)
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
        
        exit_code = self.run_cli(test_args)
        self.assertIn(exit_code, (None, 0), msg=f"CLI exit code abnormal: {exit_code}")
        
        # Should find 2 images (top-level and sub-directory)
        # 1x1 split, so 2 generated
        files = list(self.output_dir.glob("*"))
        self.assertEqual(len(files), 2)

    def test_cli_no_valid_files(self):
        """When input path has no valid images, should sys.exit(1)."""
        test_args = ["cli.py", str(self.test_dir / "nonexistent"), "-r", "2", "-c", "2"]
        
        self.assertEqual(self.run_cli(test_args), 1)

    def test_glob_excludes_directories(self):
        """Ensure wildcards don't incorrectly match directories with same names."""
        fake_dir = self.test_dir / "trap.jpg"  # Directory named .jpg
        fake_dir.mkdir()
        
        test_args = [
            "cli.py", str(self.test_dir / "*.jpg"),
            "-r", "1", "-c", "1",
            "-o", str(self.output_dir)
        ]
        
        # No valid files, should exit 1
        self.assertEqual(self.run_cli(test_args), 1)

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
        
        self.assertIn(self.run_cli(test_args), (None, 0))
                    
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
        self.assertIn(self.run_cli(test_args), (None, 0))
        self.assertTrue((self.output_dir / "test_01.png").exists())

    def test_cli_invalid_arguments(self):
        """Test invalid argument types (e.g., passing string for rows)."""
        test_args = ["cli.py", str(self.img_path), "-r", "abc", "-c", "2"]
        # argparse prints error and exits directly
        self.assertIsNotNone(self.run_cli(test_args, stderr=True))

    def test_cli_rejects_zero_jobs(self):
        """Concurrency must be greater than 0 to avoid runtime exceptions in executor layer."""
        test_args = ["cli.py", str(self.img_path), "-r", "1", "-c", "1", "-j", "0"]
        self.assertIsNotNone(self.run_cli(test_args, stderr=True))

    def test_cli_auto_create_output_dir(self):
        """Verify CLI automatically creates non-existent output directories."""
        new_dir = self.test_dir / "brand_new_dir"
        self.assertFalse(new_dir.exists())
        
        test_args = [
            "cli.py", str(self.img_path),
            "-r", "1", "-c", "1",
            "-o", str(new_dir)
        ]
        self.assertIn(self.run_cli(test_args), (None, 0))
        
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
        exit_code = self.run_cli(test_args)
        self.assertIn(exit_code, (None, 0), msg=f"CLI exit code abnormal: {exit_code}")

        self.assertTrue((self.output_dir / "test_01.jpg").exists())

    def test_cli_processor_not_found(self):
        """Unknown processor should fail explicitly and return exit code 1."""
        test_args = [
            "cli.py", str(self.img_path),
            "--processor", "not_exists_processor",
            "-o", str(self.output_dir)
        ]
        self.assertEqual(self.run_cli(test_args), 1)

    def test_cli_preset_save_and_load(self):
        """--preset-save and --preset should work end-to-end."""
        from unittest.mock import patch

        preset_name = "test_cli_3x3"
        # Isolate the presets dir — cli.main() would otherwise write into
        # the real ~/.image_splitter/presets.
        pd = self.test_dir / "presets"
        pd.mkdir()
        patcher = patch(
            "image_splitter.engine.presets._presets_dir", return_value=pd
        )
        patcher.start()
        self.addCleanup(patcher.stop)

        # Save the preset
        test_args_save = [
            "cli.py", str(self.img_path),
            "-r", "3", "-c", "3",
            "-o", str(self.output_dir),
            "-j", "1",
            "--preset-save", preset_name,
        ]
        self.run_cli(test_args_save)

        # Load the preset and verify it executes
        out2 = self.test_dir / "output_preset"
        test_args_load = [
            "cli.py", str(self.img_path),
            "--preset", preset_name,
            "-o", str(out2),
            "-j", "1",
        ]
        exit_code = self.run_cli(test_args_load)
        self.assertIn(exit_code, (None, 0),
                      f"CLI preset load exit code: {exit_code}")

        self.assertTrue(out2.exists())
        files = list(out2.glob("*.png"))
        self.assertEqual(len(files), 9, f"Expected 9 tiles, got {len(files)}")

    def test_cli_script_mode(self):
        """--script should execute a script file end-to-end."""
        script_path = self.test_dir / "test_script.txt"
        script_path.write_text(
            "grid_splitter rows=2 cols=2 output_dir=" + str(self.output_dir) + "\n"
        )
        test_args = [
            "cli.py", str(self.img_path),
            "-s", str(script_path),
            "-o", str(self.output_dir),
        ]
        exit_code = self.run_cli(test_args)
        self.assertIn(exit_code, (None, 0),
                      f"CLI script exit code: {exit_code}")

        files = list(self.output_dir.glob("*.png"))
        self.assertGreater(len(files), 0, "Script should produce output files")


if __name__ == '__main__':
    unittest.main()
