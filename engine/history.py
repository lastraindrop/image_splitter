"""Operation history stack for undo/redo awareness.

Aligns with Blender's operator log philosophy: each operation is recorded
as a reproducible HistoryEntry, enabling undo/redo and export as script.
"""
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class HistoryEntry:
    """A single recorded operation snapshot."""

    timestamp: float
    operator_name: str
    config_snapshot: Dict[str, Any]
    input_files: List[str]
    description: str


class HistoryManager:
    """Operation history manager with undo/redo support.

    Stores a bounded history of operations. Undo does not restore files
    (image files are immutable on disk); rather, it surfaces the recorded
    parameters so the user can inspect or replay them.

    Usage:
        manager = HistoryManager(max_depth=50)
        manager.push(HistoryEntry(...))
        entry = manager.undo()   # returns most recent entry
        entry = manager.redo()   # re-applies undone entry
    """

    def __init__(self, max_depth: int = 50) -> None:
        if max_depth < 1:
            raise ValueError("max_depth must be at least 1")
        self._max_depth: int = max_depth
        self._undo_stack: List[HistoryEntry] = []
        self._redo_stack: List[HistoryEntry] = []

    def push(self, entry: HistoryEntry) -> None:
        """Record a new operation onto the history stack.

        Clears the redo stack (standard undo/redo semantics).
        """
        self._redo_stack.clear()
        self._undo_stack.append(entry)
        if len(self._undo_stack) > self._max_depth:
            self._undo_stack.pop(0)

    def undo(self) -> Optional[HistoryEntry]:
        """Undo the most recent operation.

        Returns the undone HistoryEntry, or None if nothing to undo.
        """
        if not self._undo_stack:
            return None
        entry = self._undo_stack.pop()
        self._redo_stack.append(entry)
        return entry

    def redo(self) -> Optional[HistoryEntry]:
        """Redo the most recently undone operation.

        Returns the redone HistoryEntry, or None if nothing to redo.
        """
        if not self._redo_stack:
            return None
        entry = self._redo_stack.pop()
        self._undo_stack.append(entry)
        return entry

    def can_undo(self) -> bool:
        """Check if there is an operation to undo."""
        return len(self._undo_stack) > 0

    def can_redo(self) -> bool:
        """Check if there is an operation to redo."""
        return len(self._redo_stack) > 0

    def clear(self) -> None:
        """Clear both undo and redo stacks."""
        self._undo_stack.clear()
        self._redo_stack.clear()

    def get_history(self) -> List[HistoryEntry]:
        """Return a copy of the undo stack (oldest first)."""
        return list(self._undo_stack)

    def export_log(self, path: str) -> None:
        """Export the complete history as a JSON log file.

        Args:
            path: Output file path for the JSON log.
        """
        entries = []
        for entry in self._undo_stack:
            entries.append({
                "timestamp": entry.timestamp,
                "operator_name": entry.operator_name,
                "config_snapshot": entry.config_snapshot,
                "input_files": entry.input_files,
                "description": entry.description,
            })
        out_path = Path(path)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2, ensure_ascii=False)

    @property
    def undo_depth(self) -> int:
        """Number of undoable entries."""
        return len(self._undo_stack)

    @property
    def redo_depth(self) -> int:
        """Number of redoable entries."""
        return len(self._redo_stack)
