"""Tests for the operation history system (undo/redo)."""
import json
import tempfile
import time
import unittest
from pathlib import Path

from image_splitter.engine.history import HistoryEntry, HistoryManager


class TestHistory(unittest.TestCase):
    def setUp(self):
        self.manager = HistoryManager(max_depth=10)

    def _make_entry(self, name="test_op", desc="test"):
        return HistoryEntry(
            timestamp=time.time(),
            operator_name=name,
            config_snapshot={"key": "value"},
            input_files=["test.png"],
            description=desc,
        )

    def test_push_and_undo(self):
        entry = self._make_entry()
        self.manager.push(entry)
        self.assertTrue(self.manager.can_undo())
        self.assertFalse(self.manager.can_redo())

        undone = self.manager.undo()
        self.assertIsNotNone(undone)
        self.assertEqual(undone.operator_name, "test_op")
        self.assertFalse(self.manager.can_undo())
        self.assertTrue(self.manager.can_redo())

    def test_redo_after_undo(self):
        entry = self._make_entry()
        self.manager.push(entry)
        self.manager.undo()
        redone = self.manager.redo()
        self.assertIsNotNone(redone)
        self.assertEqual(redone.operator_name, "test_op")
        self.assertTrue(self.manager.can_undo())
        self.assertFalse(self.manager.can_redo())

    def test_redo_clears_on_new_push(self):
        e1 = self._make_entry("op1")
        e2 = self._make_entry("op2")
        self.manager.push(e1)
        self.manager.push(e2)
        self.manager.undo()
        self.assertTrue(self.manager.can_redo())
        e3 = self._make_entry("op3")
        self.manager.push(e3)
        self.assertFalse(self.manager.can_redo())

    def test_max_depth_eviction(self):
        small = HistoryManager(max_depth=3)
        for i in range(5):
            small.push(self._make_entry(f"op{i}"))
        self.assertEqual(small.undo_depth, 3)
        history = small.get_history()
        self.assertEqual(history[0].operator_name, "op2")
        self.assertEqual(history[-1].operator_name, "op4")

    def test_clear(self):
        self.manager.push(self._make_entry())
        self.manager.push(self._make_entry())
        self.manager.undo()
        self.manager.clear()
        self.assertFalse(self.manager.can_undo())
        self.assertFalse(self.manager.can_redo())
        self.assertEqual(self.manager.undo_depth, 0)
        self.assertEqual(self.manager.redo_depth, 0)

    def test_export_log(self):
        self.manager.push(self._make_entry("op1", "first"))
        self.manager.push(self._make_entry("op2", "second"))
        with tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, mode="w"
        ) as f:
            f.close()
            self.manager.export_log(f.name)
            with open(f.name, "r", encoding="utf-8") as rf:
                data = json.load(rf)
            self.assertEqual(len(data), 2)
            self.assertEqual(data[0]["operator_name"], "op1")
            self.assertEqual(data[1]["operator_name"], "op2")
            Path(f.name).unlink()

    def test_empty_history_undo_returns_none(self):
        self.assertIsNone(self.manager.undo())
        self.assertIsNone(self.manager.redo())
        self.assertFalse(self.manager.can_undo())
        self.assertFalse(self.manager.can_redo())

    def test_get_history_is_copy(self):
        self.manager.push(self._make_entry())
        history = self.manager.get_history()
        history.clear()
        self.assertEqual(self.manager.undo_depth, 1)

    def test_invalid_max_depth_raises(self):
        with self.assertRaises(ValueError):
            HistoryManager(max_depth=0)
        with self.assertRaises(ValueError):
            HistoryManager(max_depth=-1)

    def test_undo_depth_property(self):
        for i in range(3):
            self.manager.push(self._make_entry(f"op{i}"))
        self.assertEqual(self.manager.undo_depth, 3)
        self.manager.undo()
        self.assertEqual(self.manager.undo_depth, 2)
        self.assertEqual(self.manager.redo_depth, 1)


if __name__ == "__main__":
    unittest.main()
