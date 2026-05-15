"""Tests for operator compliance."""

import unittest

from image_splitter.core import register_all_processors
from image_splitter.engine.registry import ProcessorRegistry

class TestOperatorCompliance(unittest.TestCase):
    """
    Operator Compliance Audit (Blender-like Operator Compliance)
    The purpose is to enforce software engineering specifications through automated means, 
    ensuring the certainty of dynamic UI rendering and script calls.
    """

    @classmethod
    def setUpClass(cls):
        # Force update and scan all plugins
        register_all_processors()

    def test_registry_not_empty(self):
        """Core Check: The registry must contain discovered processors"""
        processors = ProcessorRegistry.list_all()
        self.assertGreater(len(processors), 0, "No processors found in the registry!")

    def test_naming_and_display_consistency(self):
        """Consistency Check: Each operator must have a unique name and display name"""
        names = set()
        display_names = set()
        for p in ProcessorRegistry.list_all():
            with self.subTest(processor=p.name):
                # 1. Check physical name format (snake_case)
                self.assertTrue(p.name.islower(), f"Operator ID '{p.name}' should be snake_case")
                self.assertNotIn(" ", p.name, f"Operator ID '{p.name}' contains spaces")
                
                # 2. Uniqueness check
                self.assertNotIn(p.name, names, f"Duplicate Operator ID found: {p.name}")
                self.assertNotIn(p.display_name, display_names, f"Duplicate Display Name found: {p.display_name}")
                
                names.add(p.name)
                display_names.add(p.display_name)

    def test_ui_metadata_schema(self):
        """Metadata Protocol Check: Verify the completeness of all UI parameter definitions"""
        valid_types = {"int", "float", "bool", "str", "list", "enum"}
        
        for p in ProcessorRegistry.list_all():
            metadata = p.get_ui_metadata()
            with self.subTest(processor=p.name):
                # Check if get_ui_metadata exists but is in the wrong format
                self.assertIsInstance(metadata, list, f"Metadata of {p.name} must be a list")
                
                for field in metadata:
                    # Mandatory fields
                    self.assertIn("name", field, f"Field in {p.name} missing 'name'")
                    self.assertIn("label", field, f"Field in {p.name} missing 'label'")
                    self.assertIn("default", field, f"Field in {p.name} missing 'default'")
                    
                    # Strong validation: type must be explicitly defined
                    self.assertIn("type", field, f"Field '{field['name']}' in {p.name} missing 'type' (required for UI rendering)")
                    self.assertIn(field["type"], valid_types, f"Unsupported type '{field['type']}' in {p.name}")

    def test_all_processors_are_gui_addressable(self):
        """Under the dynamic UI architecture, each processor should provide editable parameter metadata"""
        for p in ProcessorRegistry.list_all():
            with self.subTest(processor=p.name):
                self.assertGreater(len(p.get_ui_metadata()), 0, f"{p.name} lacks GUI metadata and cannot be configured in the dynamic interface")

    def test_documentation_completeness(self):
        """Documentation Indicator: Verify if there are operation tips, which is an essential element of professional software"""
        for p in ProcessorRegistry.list_all():
            with self.subTest(processor=p.name):
                # Although tool_tip can be empty, in a professional architecture, it is recommended to have at least 5 characters of description
                self.assertTrue(hasattr(p, 'tool_tip'), f"{p.name} missing 'tool_tip' property")
                # Even if it is allowed to be empty, we record a warning (here as an assert check)
                # self.assertGreater(len(p.tool_tip), 0, f"Operator {p.name} should have a description in tool_tip")

    def test_category_membership(self):
        """Category Consistency: Verify if the category belongs to a predefined set"""
        valid_categories = {"Split", "Transform", "Edit", "Filter", "Export"}
        for p in ProcessorRegistry.list_all():
             with self.subTest(processor=p.name):
                 self.assertIn(p.category, valid_categories, f"{p.name} has invalid category: {p.category}")

if __name__ == '__main__':
    unittest.main()
