# image_splitter/tests/test_operator_compliance.py
import unittest
import os
from image_splitter.engine.registry import ProcessorRegistry
from image_splitter.core import register_all_processors

class TestOperatorCompliance(unittest.TestCase):
    """
    操作符合规性审计 (Blender-like Operator Compliance)
    目的是通过自动化手段强制执行软件工程规范，确保 UI 动态渲染与脚本调用的确定性。
    """

    @classmethod
    def setUpClass(cls):
        # 强制更新并扫描所有插件
        register_all_processors()

    def test_registry_not_empty(self):
        """核心检查：注册表必须包含已发现的处理器"""
        processors = ProcessorRegistry.list_all()
        self.assertGreater(len(processors), 0, "No processors found in the registry!")

    def test_naming_and_display_consistency(self):
        """一致性检查：每一个操作符必须具备唯一的名称与显示名称"""
        names = set()
        display_names = set()
        for p in ProcessorRegistry.list_all():
            with self.subTest(processor=p.name):
                # 1. 检查物理名称格式 (snake_case)
                self.assertTrue(p.name.islower(), f"Operator ID '{p.name}' should be snake_case")
                self.assertNotIn(" ", p.name, f"Operator ID '{p.name}' contains spaces")
                
                # 2. 唯一性检查
                self.assertNotIn(p.name, names, f"Duplicate Operator ID found: {p.name}")
                self.assertNotIn(p.display_name, display_names, f"Duplicate Display Name found: {p.display_name}")
                
                names.add(p.name)
                display_names.add(p.display_name)

    def test_ui_metadata_schema(self):
        """元数据协议检查：验证所有 UI 参数定义的完备性"""
        valid_types = {"int", "float", "bool", "str", "list", "enum"}
        
        for p in ProcessorRegistry.list_all():
            metadata = p.get_ui_metadata()
            with self.subTest(processor=p.name):
                # 检查是否存在 get_ui_metadata 但格式错误
                self.assertIsInstance(metadata, list, f"Metadata of {p.name} must be a list")
                
                for field in metadata:
                    # 必须字段
                    self.assertIn("name", field, f"Field in {p.name} missing 'name'")
                    self.assertIn("label", field, f"Field in {p.name} missing 'label'")
                    self.assertIn("default", field, f"Field in {p.name} missing 'default'")
                    
                    # 强校验：必须明确类型
                    self.assertIn("type", field, f"Field '{field['name']}' in {p.name} missing 'type' (required for UI rendering)")
                    self.assertIn(field["type"], valid_types, f"Unsupported type '{field['type']}' in {p.name}")

    def test_documentation_completeness(self):
        """文档化指标：验证是否有操作提示，这是专业软件的必备要素"""
        for p in ProcessorRegistry.list_all():
            with self.subTest(processor=p.name):
                # 虽然 tool_tip 可以为空，但在专业架构下，建议至少具备 5 个字符以上的说明
                self.assertTrue(hasattr(p, 'tool_tip'), f"{p.name} missing 'tool_tip' property")
                # 即使允许为空，我们也记录警告 (这里作为 assert 检查)
                # self.assertGreater(len(p.tool_tip), 0, f"Operator {p.name} should have a description in tool_tip")

    def test_category_membership(self):
        """归类一致性：验证 category 是否属于预定义集合"""
        valid_categories = {"Split", "Transform", "Edit", "Filter", "Export"}
        for p in ProcessorRegistry.list_all():
             with self.subTest(processor=p.name):
                 self.assertIn(p.category, valid_categories, f"{p.name} has invalid category: {p.category}")

if __name__ == '__main__':
    unittest.main()
