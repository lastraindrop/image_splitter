"""Interactive command console panel for the GUI.

Aligns with Blender's Python Console / Info Editor: provides an embedded
command input area where users can type operator invocations directly.
"""
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Dict, List, Optional

from image_splitter.engine.registry import ProcessorRegistry
from image_splitter.script_engine import ScriptEngine


class ConsolePanel(ttk.Frame):
    """Embedded command console for interactive operator execution.

    Features:
        - Command input with history (up/down arrows)
        - Colored output (normal, success, error, info)
        - Tab completion for operator names
        - Direct operator invocation and chain execution

    Usage:
        console = ConsolePanel(parent, on_execute=callback)
        console.pack(fill=tk.BOTH, expand=True)
    """

    def __init__(
        self,
        parent: Any,
        script_engine: Optional[ScriptEngine] = None,
        on_execute: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        theme: Optional[Any] = None,
        font: tuple = ("Consolas", 10),
    ) -> None:
        super().__init__(parent)
        self._engine = script_engine or ScriptEngine()
        self._on_execute = on_execute
        self._history: List[str] = []
        self._history_index: int = -1
        self._font = font

        self._build_ui()

    def _build_ui(self) -> None:
        # Output area (read-only)
        self.output_frame = tk.Frame(self)
        self.output_frame.pack(fill=tk.BOTH, expand=True)

        self.output_text = tk.Text(
            self.output_frame,
            wrap=tk.WORD,
            state=tk.DISABLED,
            font=self._font,
            bg="#0d0d0d",
            fg="#d4d4d4",
            insertbackground="white",
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=0,
            padx=8,
            pady=6,
        )
        self.output_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(
            self.output_frame, orient=tk.VERTICAL, command=self.output_text.yview
        )
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.output_text.config(yscrollcommand=scrollbar.set)

        # Configure text tags
        self.output_text.tag_configure("output", foreground="#d4d4d4")
        self.output_text.tag_configure("success", foreground="#10b981")
        self.output_text.tag_configure("error", foreground="#ef4444")
        self.output_text.tag_configure("info", foreground="#3b82f6")
        self.output_text.tag_configure("prompt", foreground="#f59e0b")

        # Input area
        self.input_frame = tk.Frame(self, bg="#1a1a1a")
        self.input_frame.pack(fill=tk.X)

        tk.Label(
            self.input_frame,
            text=">>>",
            font=self._font,
            bg="#1a1a1a",
            fg="#f59e0b",
        ).pack(side=tk.LEFT, padx=(6, 4))

        self.input_entry = tk.Entry(
            self.input_frame,
            font=self._font,
            bg="#1a1a1a",
            fg="white",
            insertbackground="white",
            relief=tk.FLAT,
        )
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4, padx=(0, 6))
        self.input_entry.bind("<Return>", self._on_enter)
        self.input_entry.bind("<Up>", self._history_up)
        self.input_entry.bind("<Down>", self._history_down)
        self.input_entry.bind("<Tab>", self._tab_complete)

    def _on_enter(self, _event: Optional[tk.Event] = None) -> None:
        cmd = self.input_entry.get().strip()
        if not cmd:
            return

        self._history.append(cmd)
        self._history_index = len(self._history)
        self.input_entry.delete(0, tk.END)

        self.append_output(f">>> {cmd}\n", "prompt")

        try:
            # Try as chain command first (contains '|')
            if "|" in cmd:
                result = self._engine.chain([], cmd)
                self.append_output(f"{result.message}\n", "success")
                return

            # Try as simple operator invocation: operator_name key=value ...
            parts = cmd.split()
            if not parts:
                return

            operator = parts[0]
            config: Dict[str, Any] = {}

            for param in parts[1:]:
                if "=" in param:
                    key, value = param.split("=", 1)
                    config[key] = self._coerce_value(value)

            if self._on_execute:
                self._on_execute(operator, config)
                self.append_output(f"[OK] Dispatched: {operator}\n", "success")
            else:
                self.append_output("[INFO] No execute handler configured\n", "info")

        except Exception as e:
            self.append_output(f"[ERROR] {e}\n", "error")

    def _history_up(self, _event: Optional[tk.Event] = None) -> None:
        if not self._history:
            return
        if self._history_index > 0:
            self._history_index -= 1
            self.input_entry.delete(0, tk.END)
            self.input_entry.insert(0, self._history[self._history_index])

    def _history_down(self, _event: Optional[tk.Event] = None) -> None:
        if self._history_index < len(self._history) - 1:
            self._history_index += 1
            self.input_entry.delete(0, tk.END)
            self.input_entry.insert(0, self._history[self._history_index])
        else:
            self._history_index = len(self._history)
            self.input_entry.delete(0, tk.END)

    def _tab_complete(self, _event: Optional[tk.Event] = None) -> str:
        current = self.input_entry.get()
        if " " in current:
            return "break"

        operators = [p.name for p in ProcessorRegistry.list_all()]
        matches = [op for op in operators if op.startswith(current)]

        if len(matches) == 1:
            self.input_entry.delete(0, tk.END)
            self.input_entry.insert(0, matches[0] + " ")
        elif len(matches) > 1:
            self.append_output("\n", "info")
            self.append_output("  ".join(matches) + "\n", "info")
            self.append_output(f">>> {current}", "prompt")
            # Fill in common prefix
            common = self._common_prefix(matches)
            if common and common != current:
                self.input_entry.delete(0, tk.END)
                self.input_entry.insert(0, common)

        return "break"

    @staticmethod
    def _common_prefix(strings: List[str]) -> str:
        if not strings:
            return ""
        prefix = strings[0]
        for s in strings[1:]:
            while not s.startswith(prefix):
                prefix = prefix[:-1]
                if not prefix:
                    return ""
        return prefix

    @staticmethod
    def _coerce_value(value: str) -> Any:
        """Attempt to convert a string value to an appropriate Python type."""
        if not value:
            return ""
        if value.lower() in ("true", "yes"):
            return True
        if value.lower() in ("false", "no"):
            return False
        try:
            if "." in value:
                return float(value)
            return int(value)
        except ValueError:
            pass
        if value.startswith("[") and value.endswith("]"):
            import ast
            try:
                return ast.literal_eval(value)
            except (ValueError, SyntaxError):
                pass
        return value

    def append_output(self, text: str, tag: str = "output") -> None:
        """Append text to the output area with a color tag."""
        self.output_text.config(state=tk.NORMAL)
        self.output_text.insert(tk.END, text, tag)
        self.output_text.see(tk.END)
        self.output_text.config(state=tk.DISABLED)

    def clear_output(self) -> None:
        """Clear the output area."""
        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete("1.0", tk.END)
        self.output_text.config(state=tk.DISABLED)

    def set_engine(self, engine: ScriptEngine) -> None:
        """Replace the script engine instance."""
        self._engine = engine

    def welcome(self) -> None:
        """Display a welcome message with available operators."""
        operators = self._engine.get_available_operators()
        self.append_output("Image Splitter Pro Console\n", "success")
        self.append_output(
            f"Available operators: {', '.join(sorted(operators))}\n", "info"
        )
        self.append_output(
            'Try: grid_splitter rows=3 cols=2\n'
            '  or: resizer width=0.5 | grid_splitter rows=2 cols=2\n\n',
            "info",
        )
