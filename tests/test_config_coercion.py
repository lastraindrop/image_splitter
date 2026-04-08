import unittest

from image_splitter.engine.config_coercion import coerce_processor_config


class _DummyProcessor:
    def get_ui_metadata(self):
        return [
            {"name": "count", "label": "Count", "type": "int", "default": 1},
            {"name": "scale", "label": "Scale", "type": "float", "default": 1.0},
            {"name": "enabled", "label": "Enabled", "type": "bool", "default": False},
            {"name": "lines", "label": "Lines", "type": "list", "default": [1, 2]},
            {"name": "mode", "label": "Mode", "type": "enum", "default": "A", "options": ["A", "B"]},
            {"name": "note", "label": "Note", "type": "str", "default": "x"},
        ]


class TestConfigCoercion(unittest.TestCase):
    def test_coerce_all_supported_types(self):
        processor = _DummyProcessor()
        raw = {
            "count": "3",
            "scale": "2.5",
            "enabled": "true",
            "lines": "[10, 20]",
            "mode": "B",
            "note": 123,
            "output_dir": "./out",
        }
        cfg = coerce_processor_config(processor, raw)

        self.assertEqual(cfg["count"], 3)
        self.assertAlmostEqual(cfg["scale"], 2.5)
        self.assertTrue(cfg["enabled"])
        self.assertEqual(cfg["lines"], [10, 20])
        self.assertEqual(cfg["mode"], "B")
        self.assertEqual(cfg["note"], "123")
        self.assertEqual(cfg["output_dir"], "./out")

    def test_invalid_enum_raises_value_error(self):
        processor = _DummyProcessor()
        with self.assertRaises(ValueError):
            coerce_processor_config(processor, {"mode": "C"})

    def test_invalid_bool_raises_value_error(self):
        processor = _DummyProcessor()
        with self.assertRaises(ValueError):
            coerce_processor_config(processor, {"enabled": "maybe"})

    def test_defaults_are_applied_when_value_missing(self):
        processor = _DummyProcessor()
        cfg = coerce_processor_config(processor, {})

        self.assertEqual(cfg["count"], 1)
        self.assertEqual(cfg["scale"], 1.0)
        self.assertFalse(cfg["enabled"])
        self.assertEqual(cfg["lines"], [1, 2])
        self.assertEqual(cfg["mode"], "A")
        self.assertEqual(cfg["note"], "x")

    def test_tuple_is_coerced_to_list(self):
        processor = _DummyProcessor()
        cfg = coerce_processor_config(processor, {"lines": (7, 8)})
        self.assertEqual(cfg["lines"], [7, 8])

    def test_invalid_list_raises_value_error(self):
        processor = _DummyProcessor()
        with self.assertRaises(ValueError):
            coerce_processor_config(processor, {"lines": "not-a-list"})

    def test_false_like_bool_values_are_supported(self):
        processor = _DummyProcessor()
        cfg = coerce_processor_config(processor, {"enabled": "off"})
        self.assertFalse(cfg["enabled"])


if __name__ == "__main__":
    unittest.main()
