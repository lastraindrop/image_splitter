"""Visual pipeline editor for chaining image operators.

Provides a panel where users can compose a sequence of operations
that will be applied in order. Each step is an operator with its
own parameters.
"""
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable, Dict, List, Optional, Tuple

from image_splitter.engine.config_coercion import coerce_processor_config
from image_splitter.engine.registry import ProcessorRegistry


class PipelineStep:
    """A single step in a processing pipeline."""

    def __init__(self, processor_name: str, params: Dict[str, Any]):
        self.processor_name = processor_name
        self.params = params

    def to_spec(self) -> str:
        """Convert to dispatcher chain spec fragment."""
        parts = []
        for k, v in self.params.items():
            parts.append(f"{k}={v!r}")
        return f"{self.processor_name}({', '.join(parts)})"

    def copy(self) -> "PipelineStep":
        return PipelineStep(self.processor_name, dict(self.params))


class PipelineEditor(ttk.Frame):
    """Visual pipeline editor for composing operator chains.

    Features:
        - Add/remove/reorder operator steps
        - Edit parameters per step
        - Generate chain spec string
        - Preview step count and summary

    Usage:
        editor = PipelineEditor(parent, on_change=callback, theme=theme)
        editor.pack(fill=tk.BOTH, expand=True)
    """

    def __init__(
        self,
        parent: Any,
        on_change: Optional[Callable[[], None]] = None,
        theme: Optional[Any] = None,
        font: tuple = ("Consolas", 9),
    ) -> None:
        super().__init__(parent)
        self._steps: List[PipelineStep] = []
        self._on_change = on_change
        self._font = font
        self._step_widgets: List[tk.Frame] = []

        self._build_ui()
        self._refresh_steps()

    def _build_ui(self) -> None:
        # Toolbar
        toolbar = tk.Frame(self)
        toolbar.pack(fill=tk.X, pady=(0, 4))

        self._op_var = tk.StringVar()
        ops = [p.name for p in ProcessorRegistry.list_all()]
        self._op_combo = ttk.Combobox(
            toolbar, textvariable=self._op_var,
            values=ops, state="readonly", font=self._font, width=18,
        )
        self._op_combo.pack(side=tk.LEFT, padx=(0, 4))
        if ops:
            self._op_combo.current(0)

        tk.Button(
            toolbar, text="+ Add Step", font=self._font,
            command=self._add_step, relief="flat",
            padx=6, bg="#1e3a5f", fg="white",
        ).pack(side=tk.LEFT, padx=(0, 4))

        tk.Button(
            toolbar, text="Clear All", font=self._font,
            command=self._clear_all, relief="flat",
            padx=6, bg="#5f1e1e", fg="white",
        ).pack(side=tk.LEFT)

        self._summary_label = tk.Label(
            toolbar, text="0 steps", font=self._font,
            fg="#888888",
        )
        self._summary_label.pack(side=tk.RIGHT, padx=(4, 0))

        # Scrollable step list
        canvas_frame = tk.Frame(self)
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        self._canvas = tk.Canvas(canvas_frame, highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(
            canvas_frame, orient=tk.VERTICAL, command=self._canvas.yview
        )
        self._scroll_frame = tk.Frame(self._canvas)

        self._scroll_frame.bind(
            "<Configure>",
            lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        )

        self._canvas.create_window((0, 0), window=self._scroll_frame, anchor="nw")
        self._canvas.configure(yscrollcommand=scrollbar.set)

        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._canvas.bind("<Enter>", self._bind_mousewheel)
        self._canvas.bind("<Leave>", self._unbind_mousewheel)

    def _bind_mousewheel(self, _event: tk.Event) -> None:
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _unbind_mousewheel(self, _event: tk.Event) -> None:
        self._canvas.unbind_all("<MouseWheel>")

    def _on_mousewheel(self, event: tk.Event) -> None:
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _add_step(self) -> None:
        name = self._op_var.get()
        if not name:
            return
        try:
            proc = ProcessorRegistry.get(name)
        except ValueError:
            return

        meta = proc.get_ui_metadata()
        params: Dict[str, Any] = {}
        for m in meta:
            params[m["name"]] = m.get("default", "")

        step = PipelineStep(name, params)
        self._steps.append(step)
        self._refresh_steps()
        if self._on_change:
            self._on_change()

    def _remove_step(self, index: int) -> None:
        if 0 <= index < len(self._steps):
            del self._steps[index]
            self._refresh_steps()
            if self._on_change:
                self._on_change()

    def _move_up(self, index: int) -> None:
        if index > 0:
            self._steps[index], self._steps[index - 1] = (
                self._steps[index - 1],
                self._steps[index],
            )
            self._refresh_steps()
            if self._on_change:
                self._on_change()

    def _move_down(self, index: int) -> None:
        if index < len(self._steps) - 1:
            self._steps[index], self._steps[index + 1] = (
                self._steps[index + 1],
                self._steps[index],
            )
            self._refresh_steps()
            if self._on_change:
                self._on_change()

    def _make_edit_cmd(self, idx: int):
        def _cmd() -> None:
            self._edit_params(idx)
        return _cmd

    def _make_remove_cmd(self, idx: int):
        def _cmd() -> None:
            self._remove_step(idx)
        return _cmd

    def _make_up_cmd(self, idx: int):
        def _cmd() -> None:
            self._move_up(idx)
        return _cmd

    def _make_down_cmd(self, idx: int):
        def _cmd() -> None:
            self._move_down(idx)
        return _cmd

    def _edit_params(self, index: int) -> None:
        step = self._steps[index]
        proc = ProcessorRegistry.get(step.processor_name)
        meta = proc.get_ui_metadata()

        dialog = tk.Toplevel(self)
        dialog.title(f"Edit: {proc.display_name}")
        dialog.geometry("350x400")
        dialog.transient(self.winfo_toplevel())

        vars_map: Dict[str, tk.Variable] = {}
        row = 0
        for m in meta:
            key = m["name"]
            tk.Label(dialog, text=m.get("label", key), font=self._font).grid(
                row=row, column=0, sticky="w", padx=8, pady=4
            )
            var: tk.Variable
            if m.get("type") == "bool":
                var = tk.BooleanVar(value=bool(step.params.get(key, m["default"])))
                vars_map[key] = var
                tk.Checkbutton(dialog, variable=var).grid(
                    row=row, column=1, sticky="w", padx=8
                )
            elif m.get("type") == "enum" and m.get("options"):
                var = tk.StringVar(value=str(step.params.get(key, m["default"])))
                vars_map[key] = var
                cb = ttk.Combobox(
                    dialog, textvariable=var,
                    values=m.get("options", []), state="readonly",
                    font=self._font, width=18,
                )
                cb.grid(row=row, column=1, sticky="w", padx=8)
            else:
                var = tk.StringVar(value=str(step.params.get(key, m["default"])))
                vars_map[key] = var
                tk.Entry(dialog, textvariable=var, font=self._font, width=22).grid(
                    row=row, column=1, sticky="w", padx=8
                )
            row += 1

        def _apply() -> None:
            for key, var in vars_map.items():
                step.params[key] = var.get()
            dialog.destroy()
            self._refresh_steps()
            if self._on_change:
                self._on_change()

        tk.Button(
            dialog, text="Apply", command=_apply,
            font=self._font, padx=12, pady=4,
        ).grid(row=row, column=0, columnspan=2, pady=12)

    def _refresh_steps(self) -> None:
        for w in self._step_widgets:
            w.destroy()
        self._step_widgets.clear()

        self._summary_label.config(
            text=f"{len(self._steps)} step{'s' if len(self._steps) != 1 else ''}"
        )

        for i, step in enumerate(self._steps):
            proc = ProcessorRegistry.get(step.processor_name)

            row_frame = tk.Frame(self._scroll_frame, relief="groove", bd=1)
            row_frame.pack(fill=tk.X, pady=2, padx=2)
            self._step_widgets.append(row_frame)

            # Step number badge
            badge = tk.Label(
                row_frame, text=f" {i + 1} ",
                font=self._font, fg="white", bg="#3b82f6",
                width=3,
            )
            badge.pack(side=tk.LEFT, padx=(4, 4), pady=4)

            # Operator name
            name_label = tk.Label(
                row_frame,
                text=proc.display_name,
                font=self._font,
                fg="#e0e0e0",
                width=16, anchor="w",
            )
            name_label.pack(side=tk.LEFT, padx=(0, 4), pady=4)

            # Parameter summary
            param_str = ", ".join(
                f"{k}={v}" for k, v in step.params.items()
            )
            if len(param_str) > 30:
                param_str = param_str[:30] + "..."
            tk.Label(
                row_frame, text=param_str,
                font=(self._font[0], 8), fg="#888888",
                anchor="w",
            ).pack(side=tk.LEFT, padx=(0, 4), pady=4, fill=tk.X, expand=True)

            # Action buttons
            idx = i
            tk.Button(
                row_frame, text="Edit", font=self._font,
                command=self._make_edit_cmd(idx),
                relief="flat", padx=4, bg="#2d2d2d", fg="#e0e0e0",
            ).pack(side=tk.RIGHT, padx=(0, 2), pady=4)

            tk.Button(
                row_frame, text="x", font=self._font,
                command=self._make_remove_cmd(idx),
                relief="flat", padx=6, bg="#5f1e1e", fg="white",
            ).pack(side=tk.RIGHT, padx=(0, 0), pady=4)

            # Reorder buttons
            if i < len(self._steps) - 1:
                tk.Button(
                    row_frame, text="▼", font=(self._font[0], 7),
                    command=self._make_down_cmd(idx),
                    relief="flat", padx=3, bg="#2d2d2d", fg="#888888",
                ).pack(side=tk.RIGHT, padx=(0, 0), pady=4)

            if i > 0:
                tk.Button(
                    row_frame, text="▲", font=(self._font[0], 7),
                    command=self._make_up_cmd(idx),
                    relief="flat", padx=3, bg="#2d2d2d", fg="#888888",
                ).pack(side=tk.RIGHT, padx=(0, 0), pady=4)

    def _clear_all(self) -> None:
        if messagebox.askyesno("Clear Pipeline", "Remove all steps?"):
            self._steps.clear()
            self._refresh_steps()
            if self._on_change:
                self._on_change()

    def to_chain_spec(self) -> str:
        """Generate a chain spec string for CommandDispatcher."""
        return "|".join(s.to_spec() for s in self._steps)

    @property
    def step_count(self) -> int:
        return len(self._steps)

    @property
    def steps(self) -> List[PipelineStep]:
        return [s.copy() for s in self._steps]

    def add_step(self, processor_name: str, params: Dict[str, Any]) -> None:
        self._steps.append(PipelineStep(processor_name, params))
        self._refresh_steps()
        if self._on_change:
            self._on_change()
