"""Interactive command console panel for the GUI.

Aligns with Blender's Python Console / Info Editor: provides an embedded
command input area where users can type operator invocations directly.
"""

from typing import Any, Callable, Dict, List, Optional

import customtkinter as ctk

from image_splitter.engine.registry import ProcessorRegistry
from image_splitter.script_engine import ScriptEngine


class ConsolePanel(ctk.CTkFrame):
    """Embedded command console for interactive operator execution.

    Features:
        - Command input with history (up/down arrows)
        - Colored output (normal, success, error, info)
        - Tab completion for operator names
        - Direct operator invocation and chain execution

    Usage:
        console = ConsolePanel(parent, on_execute=callback)
        console.pack(fill="both", expand=True)
    """

    def __init__(
        self,
        parent: Any,
        script_engine: Optional[ScriptEngine] = None,
        on_execute: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        theme: Optional[Any] = None,
        font: tuple = ("Consolas", 10),
        get_current_files: Optional[Callable[[], List[str]]] = None,
    ) -> None:
        super().__init__(parent)
        self._engine = script_engine or ScriptEngine()
        self._on_execute = on_execute
        self._get_current_files = get_current_files
        self._history: List[str] = []
        self._history_index: int = -1
        self._font = font
        self._theme = theme

        self._build_ui()

    def _c(self, attr: str, fallback: str) -> str:
        """Get a theme color or return a fallback."""
        if self._theme is not None:
            return getattr(self._theme, attr, fallback)
        return fallback

    def _build_ui(self) -> None:
        console_bg = self._c("CONSOLE_BG", "#0d0d0d")
        input_bg = self._c("INPUT_BG", "#1a1a1a")
        prompt_fg = self._c("PROMPT", "#f59e0b")
        output_fg = self._c("DARK_FG", "#d4d4d4")
        success_fg = self._c("SUCCESS", "#10b981")
        error_fg = self._c("DANGER", "#ef4444")
        info_fg = self._c("ACCENT", "#3b82f6")

        # Output area (read-only CTkTextbox with built-in scrollbar)
        self.output_text = ctk.CTkTextbox(
            self,
            wrap="word",
            font=self._font,
            fg_color=console_bg,
            text_color=output_fg,
            border_width=0,
            activate_scrollbars=True,
        )
        self.output_text.pack(fill="both", expand=True, padx=0, pady=(0, 0))
        self.output_text.configure(state="disabled")

        # Configure text tags
        self.output_text.tag_config("output", foreground=output_fg)
        self.output_text.tag_config("success", foreground=success_fg)
        self.output_text.tag_config("error", foreground=error_fg)
        self.output_text.tag_config("warn", foreground=prompt_fg)
        self.output_text.tag_config("info", foreground=info_fg)
        self.output_text.tag_config("prompt", foreground=prompt_fg)

        # Input area
        self.input_frame = ctk.CTkFrame(self, fg_color=input_bg)
        self.input_frame.pack(fill="x")

        ctk.CTkLabel(
            self.input_frame,
            text=">>>",
            font=self._font,
            text_color=prompt_fg,
        ).pack(side="left", padx=(6, 4))

        self.input_entry = ctk.CTkEntry(
            self.input_frame,
            font=self._font,
            fg_color=input_bg,
            text_color="white",
            border_width=0,
        )
        self.input_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.input_entry.bind("<Return>", self._on_enter)
        self.input_entry.bind("<Up>", self._history_up)
        self.input_entry.bind("<Down>", self._history_down)
        self.input_entry.bind("<Tab>", self._tab_complete)

    def _on_enter(self, _event: Any = None) -> None:
        cmd = self.input_entry.get().strip()
        if not cmd:
            return

        self._history.append(cmd)
        self._history_index = len(self._history)
        self.input_entry.delete(0, "end")

        self.append_output(f">>> {cmd}\n", "prompt")

        try:
            # Try as chain command first (contains '|')
            if "|" in cmd:
                current_files = self._get_current_files() if self._get_current_files else []
                if current_files:
                    result = self._engine.chain(current_files, cmd)
                    self.append_output(f"{result.message}\n", "success")
                else:
                    self.append_output("[INFO] No files loaded — use Load button first\n", "info")
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

    def _history_up(self, _event: Any = None) -> None:
        if not self._history:
            return
        if self._history_index > 0:
            self._history_index -= 1
            self.input_entry.delete(0, "end")
            self.input_entry.insert(0, self._history[self._history_index])

    def _history_down(self, _event: Any = None) -> None:
        if self._history_index < len(self._history) - 1:
            self._history_index += 1
            self.input_entry.delete(0, "end")
            self.input_entry.insert(0, self._history[self._history_index])
        else:
            self._history_index = len(self._history)
            self.input_entry.delete(0, "end")

    def _tab_complete(self, _event: Any = None) -> str:
        current = self.input_entry.get()
        if " " in current:
            return "break"

        operators = [p.name for p in ProcessorRegistry.list_all()]
        matches = [op for op in operators if op.startswith(current)]

        if len(matches) == 1:
            self.input_entry.delete(0, "end")
            self.input_entry.insert(0, matches[0] + " ")
        elif len(matches) > 1:
            self.append_output("\n", "info")
            self.append_output("  ".join(matches) + "\n", "info")
            self.append_output(f">>> {current}", "prompt")
            common = self._common_prefix(matches)
            if common and common != current:
                self.input_entry.delete(0, "end")
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
        self.output_text.configure(state="normal")
        self.output_text.insert("end", text, tag)
        self.output_text.see("end")
        self.output_text.configure(state="disabled")

    def clear_output(self) -> None:
        """Clear the output area."""
        self.output_text.configure(state="normal")
        self.output_text.delete("1.0", "end")
        self.output_text.configure(state="disabled")

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
        sample_ops = sorted(operators)[:2]
        if len(sample_ops) >= 2:
            self.append_output(
                f"Try: {sample_ops[0]} key=value\n"
                f"  or: {sample_ops[0]} key=value | {sample_ops[1]} key=value\n\n",
                "info",
            )
        elif sample_ops:
            self.append_output(
                f"Try: {sample_ops[0]} key=value\n\n", "info"
            )
