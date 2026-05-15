"""Tests for parameter contract."""

import unittest

from image_splitter.engine.config_coercion import coerce_processor_config
from image_splitter.engine.registry import ProcessorRegistry
from image_splitter.core import register_all_processors


class TestParameterContract(unittest.TestCase):
    def setUp(self):
        # Ensure processors are discovered afresh for test isolation
        register_all_processors()

    def test_metadata_has_name_type_and_default(self):
        for p in ProcessorRegistry.list_all():
            metadata = p.get_ui_metadata()
            for m in metadata:
                self.assertIn("name", m, f"{p.name} missing metadata 'name'")
                self.assertIn("type", m, f"{p.name} metadata 'type' missing for {m.get('name')}")
                self.assertIn("default", m, f"{p.name} metadata 'default' missing for {m.get('name')}")

    def test_coercion_with_defaults_does_not_raise_and_types_match(self):
        for p in ProcessorRegistry.list_all():
            metadata = p.get_ui_metadata()
            cfg = coerce_processor_config(p, {})
            for m in metadata:
                key = m['name']
                self.assertIn(key, cfg, f"{p.name} coercion missing key {key}")
                val = cfg[key]
                typ = m.get('type', 'str')
                if typ == 'int':
                    self.assertIsInstance(val, int, f"{p.name}:{key} expected int")
                elif typ == 'float':
                    self.assertIsInstance(val, float, f"{p.name}:{key} expected float")
                elif typ == 'bool':
                    self.assertIsInstance(val, bool, f"{p.name}:{key} expected bool")
                elif typ == 'list':
                    self.assertIsInstance(val, list, f"{p.name}:{key} expected list")
                elif typ == 'enum':
                    self.assertIsInstance(val, str, f"{p.name}:{key} expected str (enum)")
                else:
                    # default to string-like for other types
                    self.assertIsInstance(val, str, f"{p.name}:{key} expected str by default")


if __name__ == '__main__':
    unittest.main()
