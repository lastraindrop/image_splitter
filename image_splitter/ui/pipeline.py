"""Visual pipeline editor for chaining image operators.

Provides a panel where users can compose a sequence of operations
that will be applied in order. Each step is an operator with its
own parameters.
"""

from typing import Any, Callable, Dict, List, Optional

import customtkinter as ctk
from tkinter import messagebox

from image_splitter.engine.registry import ProcessorRegistry
from image_splitter.ui.param_widgets import create_param_widget


class PipelineStep:
    """A single step in a processing pipeline."""

    def __init__(self, processor_name: str, params: Dict[str, Any]):
        self.processor_name = processor_name
        self.params = params

    def to_spec(self) -> str:
        """Convert to dispatcher chain spec fragment.

        Parameters with ``None`` values are skipped — ``repr(None)`` would
        render as the bare identifier ``None``, which the dispatcher would
        parse as the *string* ``"None"`` and downstream type coercion
        would reject it.
        """
        parts = [f"{k}={v!r}" for k, v in self.params.items() if v is not None]
        return f"{self.processor_name}({', '.join(parts)})"

    def copy(self) -> "PipelineStep":
        return PipelineStep(self.processor_name, dict(self.params))


class PipelineEditor(ctk.CTkFrame):
    """Visual pipeline editor for composing operator chains.

    Features:
        - Add/remove/reorder operator steps
        - Edit parameters per step
        - Generate chain spec string
        - Preview step count and summary

    Usage:
        editor = PipelineEditor(parent, on_change=callback, theme=theme)
        editor.pack(fill="both", expand=True)
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
        self._theme = theme
        self._step_widgets: List[ctk.CTkFrame] = []

        self._build_ui()
        self._refresh_steps()

    def _c(self, attr: str, fallback: str) -> str:
        if self._theme is not None:
            return getattr(self._theme, attr, fallback)
        return fallback

    def _build_ui(self) -> None:
        add_bg = self._c("ADD_STEP_BG", "#1e3a5f")
        remove_bg = self._c("REMOVE_BG", "#5f1e1e")
        dim_fg = self._c("DIM_FG", "#888888")

        # Toolbar
        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", pady=(0, 4))

        ops = [p.name for p in ProcessorRegistry.list_all()]
        self._op_combo = ctk.CTkComboBox(
            toolbar,
            values=ops,
            font=self._font,
            width=180,
        )
        self._op_combo.pack(side="left", padx=(0, 4))
        if ops:
            self._op_combo.set(ops[0])

        ctk.CTkButton(
            toolbar, text="+ Add Step", font=self._font,
            command=self._add_step, fg_color=add_bg,
            width=90, height=28,
        ).pack(side="left", padx=(0, 4))

        ctk.CTkButton(
            toolbar, text="Clear All", font=self._font,
            command=self._clear_all, fg_color=remove_bg,
            width=70, height=28,
        ).pack(side="left")

        self._summary_label = ctk.CTkLabel(
            toolbar, text="0 steps", font=self._font,
            text_color=dim_fg,
        )
        self._summary_label.pack(side="right", padx=(4, 0))

        # Scrollable step list (replaces Canvas + Scrollbar)
        self._scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll_frame.pack(fill="both", expand=True)

    def _add_step(self) -> None:
        name = self._op_combo.get()
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

    def _make_cmd(self, idx: int, action: Callable[[int], None]):
        return lambda: action(idx)

    def _edit_params(self, index: int) -> None:
        step = self._steps[index]
        proc = ProcessorRegistry.get(step.processor_name)
        meta = proc.get_ui_metadata()

        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Edit: {proc.display_name}")
        dialog.geometry("400x450")
        dialog.transient(self.winfo_toplevel())

        widgets: Dict[str, Any] = {}
        row = 0
        for m in meta:
            key = m["name"]
            ctk.CTkLabel(dialog, text=m.get("label", key), font=self._font).grid(
                row=row, column=0, sticky="w", padx=10, pady=4
            )
            name, widget = create_param_widget(
                dialog, m,
                value=step.params.get(key),
                font=self._font,
                theme=self._theme,
            )
            widget.grid(row=row, column=1, sticky="w", padx=10)
            widgets[key] = widget
            row += 1

        def _apply() -> None:
            for key, w in widgets.items():
                val = w.get()
                if isinstance(val, str):
                    val = val.strip()
                step.params[key] = val
            dialog.destroy()
            self._refresh_steps()
            if self._on_change:
                self._on_change()

        ctk.CTkButton(
            dialog, text="Apply", command=_apply,
            font=self._font, width=100, height=32,
        ).grid(row=row, column=0, columnspan=2, pady=15)

    def _refresh_steps(self) -> None:
        for w in self._step_widgets:
            w.destroy()
        self._step_widgets.clear()

        accent = self._c("ACCENT", "#3b82f6")
        dark_fg = self._c("DARK_FG", "#e0e0e0")
        dim_fg = self._c("DIM_FG", "#888888")
        item_bg = self._c("ITEM_BG", "#2d2d2d")
        remove_bg = self._c("REMOVE_BG", "#5f1e1e")

        self._summary_label.configure(
            text=f"{len(self._steps)} step{'s' if len(self._steps) != 1 else ''}"
        )

        for i, step in enumerate(self._steps):
            proc = ProcessorRegistry.get(step.processor_name)

            row_frame = ctk.CTkFrame(
                self._scroll_frame, fg_color=item_bg,
                border_width=1, border_color=dim_fg,
            )
            row_frame.pack(fill="x", pady=2, padx=2)
            self._step_widgets.append(row_frame)

            # Step number badge
            badge = ctk.CTkLabel(
                row_frame, text=f" {i + 1} ",
                font=self._font, text_color="white",
                fg_color=accent, width=30, corner_radius=4,
            )
            badge.pack(side="left", padx=(6, 6), pady=6)

            # Operator name
            ctk.CTkLabel(
                row_frame,
                text=proc.display_name,
                font=self._font,
                text_color=dark_fg,
                width=120, anchor="w",
            ).pack(side="left", padx=(0, 4), pady=6)

            # Parameter summary
            param_str = ", ".join(
                f"{k}={v}" for k, v in step.params.items()
            )
            if len(param_str) > 30:
                param_str = param_str[:30] + "..."
            ctk.CTkLabel(
                row_frame, text=param_str,
                font=(self._font[0], 8), text_color=dim_fg,
                anchor="w",
            ).pack(side="left", padx=(0, 4), pady=6, fill="x", expand=True)

            # Action buttons (right side)
            idx = i
            ctk.CTkButton(
                row_frame, text="Edit", font=self._font,
                command=self._make_cmd(idx, self._edit_params),
                fg_color=item_bg, text_color=dark_fg,
                width=40, height=24,
            ).pack(side="right", padx=(0, 4), pady=6)

            ctk.CTkButton(
                row_frame, text="✕", font=self._font,
                command=self._make_cmd(idx, self._remove_step),
                fg_color=remove_bg, text_color="white",
                width=24, height=24,
            ).pack(side="right", padx=(0, 2), pady=6)

            if i < len(self._steps) - 1:
                ctk.CTkButton(
                    row_frame, text="▼", font=(self._font[0], 8),
                    command=self._make_cmd(idx, self._move_down),
                    fg_color=item_bg, text_color=dim_fg,
                    width=24, height=24,
                ).pack(side="right", padx=(0, 2), pady=6)

            if i > 0:
                ctk.CTkButton(
                    row_frame, text="▲", font=(self._font[0], 8),
                    command=self._make_cmd(idx, self._move_up),
                    fg_color=item_bg, text_color=dim_fg,
                    width=24, height=24,
                ).pack(side="right", padx=(0, 2), pady=6)

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
