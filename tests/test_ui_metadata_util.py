"""Tests for ui_metadata_from_dataclass — auto-generates UI metadata."""

import unittest
from dataclasses import dataclass, field

from image_splitter.engine._ui_metadata_util import ui_metadata_from_dataclass


class TestUiMetadataUtil(unittest.TestCase):
    """Verify auto-generation of UI metadata from dataclass fields."""

    def test_basic_types(self):
        @dataclass
        class Config:
            count: int = field(default=42, metadata={"label": "Count"})
            scale: float = field(default=1.0, metadata={"label": "Scale"})
            enabled: bool = field(default=False, metadata={"label": "Enabled"})
            name: str = field(default="", metadata={"label": "Name"})
            items: list = field(default_factory=list, metadata={"label": "Items"})

        meta = ui_metadata_from_dataclass(Config)
        meta_by_name = {m["name"]: m for m in meta}

        self.assertEqual(len(meta), 5)
        self.assertEqual(meta_by_name["count"]["type"], "int")
        self.assertEqual(meta_by_name["count"]["default"], 42)
        self.assertEqual(meta_by_name["scale"]["type"], "float")
        self.assertEqual(meta_by_name["enabled"]["type"], "bool")
        self.assertEqual(meta_by_name["name"]["type"], "str")
        self.assertEqual(meta_by_name["items"]["type"], "list")

    def test_enum_with_options(self):
        @dataclass
        class Config:
            mode: str = field(default="A", metadata={
                "label": "Mode", "options": ["A", "B", "C"]
            })

        meta = ui_metadata_from_dataclass(Config)
        self.assertEqual(len(meta), 1)
        self.assertEqual(meta[0]["type"], "enum")
        self.assertEqual(meta[0]["options"], ["A", "B", "C"])

    def test_skip_fields_without_label(self):
        @dataclass
        class Config:
            visible: int = field(default=1, metadata={"label": "Visible"})
            hidden: str = ""  # no label
            also_hidden: int = 0  # no label

        meta = ui_metadata_from_dataclass(Config)
        self.assertEqual(len(meta), 1)
        self.assertEqual(meta[0]["name"], "visible")

    def test_default_factory(self):
        @dataclass
        class Config:
            ratios: list = field(
                default_factory=lambda: [1, 2, 3],
                metadata={"label": "Ratios"},
            )

        meta = ui_metadata_from_dataclass(Config)
        self.assertEqual(meta[0]["default"], [1, 2, 3])

    def test_min_max_bounds(self):
        @dataclass
        class Config:
            quality: int = field(default=80, metadata={
                "label": "Quality", "min": 1, "max": 100,
            })

        meta = ui_metadata_from_dataclass(Config)
        self.assertEqual(meta[0]["min"], 1)
        self.assertEqual(meta[0]["max"], 100)

    def test_no_metadata_fields_skipped(self):
        @dataclass
        class Config:
            a: int = 1
            b: str = "x"

        meta = ui_metadata_from_dataclass(Config)
        self.assertEqual(len(meta), 0)

    def test_empty_dataclass(self):
        @dataclass
        class Config:
            pass

        meta = ui_metadata_from_dataclass(Config)
        self.assertEqual(len(meta), 0)


if __name__ == "__main__":
    unittest.main()
