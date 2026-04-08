import tempfile
import unittest
from pathlib import Path

from PIL import Image

from image_splitter.core import process_image, register_all_processors


class TestSaveCompatibility(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        register_all_processors()

    def setUp(self):
        self._temp_dir_obj = tempfile.TemporaryDirectory()
        self.test_dir = Path(self._temp_dir_obj.name)
        self.output_dir = self.test_dir / "output"
        self.output_dir.mkdir(exist_ok=True)

    def tearDown(self):
        self._temp_dir_obj.cleanup()

    def test_metadata_cleaner_preserves_icc_profile_when_requested(self):
        src = self.test_dir / "icc.png"
        Image.new("RGB", (16, 16), color="green").save(src, icc_profile=b"fake-icc-profile")

        success, msg = process_image(str(src), "metadata_cleaner", {
            "strip_all": True,
            "keep_icc": True,
            "output_dir": str(self.output_dir),
            "template": "icc_clean",
        })
        self.assertTrue(success, msg)

        with Image.open(self.output_dir / "icc_clean.png") as saved:
            self.assertEqual(saved.info.get("icc_profile"), b"fake-icc-profile")

    def test_format_converter_changes_extension_for_png_output(self):
        src = self.test_dir / "source.jpg"
        Image.new("RGB", (16, 16), color="purple").save(src)

        success, msg = process_image(str(src), "format_converter", {
            "format": "PNG",
            "quality": 80,
            "output_dir": str(self.output_dir),
            "template": "converted_png",
        })
        self.assertTrue(success, msg)
        self.assertTrue((self.output_dir / "converted_png.png").exists())


if __name__ == "__main__":
    unittest.main()