"""Operator compliance and parameter contract verification.

Ensures all processors meet the metadata protocol, have valid categories,
consistent naming, and that every parameter is coercible from defaults.
"""
from image_splitter.engine.config_coercion import coerce_processor_config
from image_splitter.engine.registry import ProcessorRegistry

from .conftest import BaseTest

VALID_TYPES = {"int", "float", "bool", "str", "list", "enum"}
VALID_CATEGORIES = {"Split", "Transform", "Edit", "Filter", "Export"}


class TestOperatorCompliance(BaseTest):
    """Blender-like operator compliance audit — ensures every processor
    is GUI-addressable, script-invokable, and metadata-complete."""

    def test_registry_not_empty(self) -> None:
        self.assertGreater(len(ProcessorRegistry.list_all()), 0)

    def test_naming_and_display_consistency(self) -> None:
        names: set[str] = set()
        display_names: set[str] = set()
        for p in ProcessorRegistry.list_all():
            with self.subTest(processor=p.name):
                self.assertTrue(p.name.islower(), f"{p.name} must be snake_case")
                self.assertNotIn(" ", p.name, f"{p.name} must not contain spaces")
                self.assertNotIn(p.name, names, f"Duplicate name: {p.name}")
                self.assertNotIn(p.display_name, display_names,
                                 f"Duplicate display_name: {p.display_name}")
                names.add(p.name)
                display_names.add(p.display_name)

    def test_ui_metadata_schema(self) -> None:
        for p in ProcessorRegistry.list_all():
            metadata = p.get_ui_metadata()
            with self.subTest(processor=p.name):
                self.assertIsInstance(metadata, list)
                for field in metadata:
                    for key in ("name", "label", "default", "type"):
                        self.assertIn(key, field,
                                      f"{p.name} field missing '{key}'")
                    self.assertIn(field["type"], VALID_TYPES,
                                  f"{p.name} invalid type: {field['type']}")

    def test_all_processors_are_gui_addressable(self) -> None:
        for p in ProcessorRegistry.list_all():
            with self.subTest(processor=p.name):
                self.assertGreater(len(p.get_ui_metadata()), 0)

    def test_documentation_completeness(self) -> None:
        for p in ProcessorRegistry.list_all():
            with self.subTest(processor=p.name):
                self.assertTrue(hasattr(p, 'tool_tip'))

    def test_category_membership(self) -> None:
        for p in ProcessorRegistry.list_all():
            with self.subTest(processor=p.name):
                self.assertIn(p.category, VALID_CATEGORIES,
                              f"{p.name} category '{p.category}' invalid")

    # ----------------------------------------------------------------
    # Parameter contract: every param must be coercible from defaults
    # ----------------------------------------------------------------
    TYPE_MAP = {"int": int, "float": float, "bool": bool,
                "list": list, "enum": str, "str": str}

    def test_metadata_has_name_type_and_default(self) -> None:
        for p in ProcessorRegistry.list_all():
            for field in p.get_ui_metadata():
                with self.subTest(proc=p.name, field=field.get("name", "?")):
                    self.assertIn("name", field)
                    self.assertIn("type", field)
                    self.assertIn("default", field)

    def test_coercion_with_defaults_produces_correct_types(self) -> None:
        for p in ProcessorRegistry.list_all():
            with self.subTest(processor=p.name):
                coerced = coerce_processor_config(p, {})
                for field in p.get_ui_metadata():
                    name = field["name"]
                    expected_type = self.TYPE_MAP.get(field["type"], str)
                    self.assertIn(name, coerced,
                                  f"Coerced missing field '{name}' in {p.name}")
                    self.assertIsInstance(coerced[name], expected_type,
                                          f"{p.name}.{name} type mismatch")


if __name__ == '__main__':
    import unittest
    unittest.main()
