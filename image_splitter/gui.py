"""Graphical user interface for Image Splitter Pro.

Uses customtkinter for modern appearance with minimal migration cost
from raw Tkinter.  All Canvas drawing code is unchanged (CTkCanvas
is a tk.Canvas subclass).

Architecture
------------
GuiState (ui/_state.py) holds all observable state as plain Python types.
Widget callbacks mutate state → state._notify() → _sync_ui_from_state()
reads state → updates widgets.  Business logic reads from state directly,
never from widget variables.

Migration to Dear PyGui: replace this file's View layer; GuiState and
engine/ require zero changes.
"""

import ast
import logging
import os
import platform
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import customtkinter as ctk
from PIL import Image
from tkinter import filedialog, messagebox

from image_splitter import keymap, settings
from image_splitter.core import register_all_processors
from image_splitter.engine.config_coercion import coerce_processor_config
from image_splitter.engine.history import HistoryEntry, HistoryManager
from image_splitter.engine.macro import MacroRecorder
from image_splitter.engine.presets import (
    delete_preset, list_presets, load_preset, save_preset,
)
from image_splitter.engine.registry import ProcessorRegistry
from image_splitter.logging_config import setup_default_logging
from image_splitter.script_engine import ScriptEngine
from image_splitter.ui._state import GuiState
from image_splitter.ui.console import ConsolePanel
from image_splitter.ui.param_widgets import create_param_widget
from image_splitter.ui.pipeline import PipelineEditor

logger = logging.getLogger(__name__)

_CANVAS_BG = "#0a0a0a"


def _detect_ui_font() -> str:
    system = platform.system()
    if system == "Windows":
        return "Microsoft YaHei UI"
    elif system == "Darwin":
        return "PingFang SC"
    else:
        return "Noto Sans CJK SC"


def _detect_mono_font() -> str:
    system = platform.system()
    if system == "Windows":
        return "Consolas"
    elif system == "Darwin":
        return "Menlo"
    else:
        return "DejaVu Sans Mono"


# Legacy theme colour constants — still used by ConsolePanel and PipelineEditor
# which accept an optional ``theme`` parameter with colour attributes.
class UITheme:
    DARK_BG = "#121212"
    PANEL_BG = "#1e1e1e"
    ITEM_BG = "#2d2d2d"
    DARK_FG = "#e0e0e0"
    DIM_FG = "#888888"
    ACCENT = "#3b82f6"
    ACCENT_ACTIVE = "#2563eb"
    SUCCESS = "#10b981"
    DANGER = "#ef4444"
    BORDER = "#333333"
    SELECT = "#264f78"
    CANVAS = _CANVAS_BG
    SECTION_HEADER = "#60a5fa"  # lighter blue — distinct from interactive accent
    PRIMARY = "#3b82f6"
    INFO = "#3b82f6"
    PROMPT = "#f59e0b"
    CONSOLE_BG = "#0d0d0d"
    INPUT_BG = "#1a1a1a"
    ADD_STEP_BG = "#1e3a5f"
    REMOVE_BG = "#5f1e1e"
    BUTTON_HOVER = "#3d3d3d"


class ImageSplitterApp:
    """Main GUI application class."""

    def __init__(self, root: ctk.CTk) -> None:
        self.root = root
        self.root.title("Image Splitter Pro")

        # customtkinter theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.ui_font = _detect_ui_font()
        self.mono_font = _detect_mono_font()
        self.theme = UITheme()  # colour constants for sub-panels

        loaded_settings = settings.load_settings()

        # Restore saved window geometry, or fall back to a sensible default.
        _saved_geo = loaded_settings.get("window_geometry", "")
        self.root.geometry(_saved_geo if _saved_geo else "1100x820")

        # ---- State layer (framework-agnostic ViewModel) ----
        self.state = GuiState()
        self.state.on_state_changed = self._sync_ui_from_state

        self.current_orig_size: Tuple[int, int] = (0, 0)
        self.thumb_img: Optional[Image.Image] = None
        self.preview_ratio: float = 1.0
        self.stop_event = threading.Event()
        self._resize_after_id: Optional[str] = None
        self._drag_guide: Optional[dict] = None
        self._last_output_dir = loaded_settings.get("output_dir", "./output")

        # Blender-aligned core systems
        self.history = HistoryManager(max_depth=50)
        self.macro = MacroRecorder()
        self.script_engine = ScriptEngine()

        # P1-7: Track param widgets so preset loading can refresh display.
        self._param_widgets: dict[str, Any] = {}
        # P1-8: Prevent concurrent batch / console / pipeline operations.
        self._busy: bool = False

        register_all_processors()
        self._create_widgets()

        # Initialise state from defaults
        # V14-6: honour the persisted template instead of the hardcoded
        # GuiState default (on_close writes it back — read/write symmetry).
        self.state.output_template = loaded_settings.get(
            "template", self.state.output_template
        )
        processors = ProcessorRegistry.list_all()
        if processors:
            # V15: honour the persisted default_processor (falling back to
            # the first registered one) AND build the parameter panel —
            # previously __init__ only called state.set_processor(), which
            # updates the combo label but leaves the Parameters panel
            # empty until the user manually re-picks an operator.
            default_name = loaded_settings.get("default_processor", "")
            startup = next(
                (p for p in processors if p.name == default_name), processors[0]
            )
            self._on_processor_changed(startup.display_name)
        self.state.plugin_count = len(processors)
        self._sync_ui_from_state()

    # ------------------------------------------------------------------
    # Font helpers
    # ------------------------------------------------------------------
    def _font(self, size: int = 10, bold: bool = False) -> Tuple[str, int, str]:
        weight = "bold" if bold else "normal"
        return (self.ui_font, size, weight)

    def _mono(self, size: int = 10) -> Tuple[str, int]:
        return (self.mono_font, size)

    # ------------------------------------------------------------------
    # Widget creation (replaces PanedWindow with grid layout)
    # ------------------------------------------------------------------
    def _create_widgets(self) -> None:
        self.main_container = ctk.CTkFrame(self.root, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True)

        # Grid replaces PanedWindow
        self.main_container.grid_columnconfigure(0, weight=0, minsize=350)
        self.main_container.grid_columnconfigure(1, weight=1)
        self.main_container.grid_rowconfigure(0, weight=1)

        self._create_left_panel()
        self._create_right_widgets()
        self._create_console_panel()
        self._create_pipeline_panel()
        self._create_status_bar()
        self._bind_keymap()

    # ------------------------------------------------------------------
    # Left panel — operator selector, params, output, buttons
    # ------------------------------------------------------------------
    def _create_left_panel(self) -> None:
        self.left_panel = ctk.CTkFrame(self.main_container, width=350)
        self.left_panel.grid(row=0, column=0, sticky="nsw", padx=(10, 5), pady=10)
        self.left_panel.grid_propagate(False)

        self.p_inner = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        self.p_inner.pack(fill="both", expand=True, padx=15, pady=10)

        ctk.CTkLabel(self.p_inner, text="Operators",
                     font=ctk.CTkFont(family=self.ui_font, size=11, weight="bold"),
                     text_color=self.theme.SECTION_HEADER).pack(pady=(10, 5), anchor="w")

        ops = [p.display_name for p in ProcessorRegistry.list_all()]
        self.processor_combo = ctk.CTkComboBox(
            self.p_inner, values=ops, font=self._font(10),
            command=self._on_processor_changed,
        )
        self.processor_combo.pack(fill="x", pady=(0, 5))

        self.tool_tip_label = ctk.CTkLabel(
            self.p_inner, text="", wraplength=310, font=self._font(9),
            text_color=self.theme.DIM_FG,
        )
        self.tool_tip_label.pack(anchor="w", fill="x", pady=(0, 10))

        # Presets
        preset_frame = ctk.CTkFrame(self.p_inner, fg_color="transparent")
        preset_frame.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(preset_frame, text="Preset:",
                     font=self._font(9), text_color=self.theme.DIM_FG).pack(side="left")
        self.preset_combo = ctk.CTkComboBox(
            preset_frame, values=[], font=self._font(10),
            command=self._on_preset_selected,
        )
        self.preset_combo.pack(side="left", padx=(4, 4), fill="x", expand=True)
        ctk.CTkButton(preset_frame, text="Save", font=self._font(9),
                      command=self._save_preset, width=45, height=26).pack(side="left", padx=(0, 2))
        ctk.CTkButton(preset_frame, text="Del", font=self._font(9),
                      command=self._delete_preset, fg_color=self.theme.REMOVE_BG,
                      width=35, height=26).pack(side="left")
        self._refresh_preset_list()

        # Separator
        ctk.CTkFrame(self.p_inner, height=1, fg_color=self.theme.BORDER).pack(fill="x", pady=10)

        # Parameters
        ctk.CTkLabel(self.p_inner, text="Parameters",
                     font=ctk.CTkFont(family=self.ui_font, size=11, weight="bold"),
                     text_color=self.theme.SECTION_HEADER).pack(pady=(10, 5), anchor="w")
        self.props_frame = ctk.CTkFrame(self.p_inner, fg_color="transparent")
        self.props_frame.pack(fill="both", expand=True, pady=5)

        ctk.CTkFrame(self.p_inner, height=1, fg_color=self.theme.BORDER).pack(fill="x", pady=10)

        # Output
        ctk.CTkLabel(self.p_inner, text="Output",
                     font=ctk.CTkFont(family=self.ui_font, size=11, weight="bold"),
                     text_color=self.theme.SECTION_HEADER).pack(pady=(10, 5), anchor="w")
        ctk.CTkLabel(self.p_inner, text="Template:",
                     font=self._font(9), text_color=self.theme.DIM_FG).pack(anchor="w")
        self.template_entry = ctk.CTkEntry(
            self.p_inner, font=self._font(10),
        )
        self.template_entry.pack(fill="x", pady=(5, 2))
        self.template_entry.insert(0, "{filename}_{index}")
        ctk.CTkLabel(self.p_inner,
                     text="Vars: {filename} {index} {row} {col} {w} {h} {ext} {anchor}",
                     font=self._font(8), text_color=self.theme.DIM_FG).pack(anchor="w", pady=(0, 10))

        # Buttons
        self.bottom_btn_frame = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        self.bottom_btn_frame.pack(side="bottom", fill="x", pady=20, padx=20)

        self.btn_run = ctk.CTkButton(
            self.bottom_btn_frame, text="Run (Ctrl+Enter)", font=self._font(10, bold=True),
            command=self.run_batch, fg_color=self.theme.ACCENT,
        )
        self.btn_run.pack(fill="x", pady=(3, 6))

        # Separator between primary action and secondary actions
        ctk.CTkFrame(self.bottom_btn_frame, height=1,
                     fg_color=self.theme.BORDER).pack(fill="x", pady=(0, 6))

        self.btn_open_out = ctk.CTkButton(
            self.bottom_btn_frame, text="Open Output Dir", font=self._font(10),
            command=self.open_output_dir, fg_color=self.theme.ITEM_BG,
        )
        self.btn_open_out.pack(fill="x", pady=3)

        self.btn_macro = ctk.CTkButton(
            self.bottom_btn_frame, text="Record Macro (Ctrl+Shift+R)", font=self._font(10),
            command=self.toggle_macro_record, fg_color=self.theme.ITEM_BG,
        )
        self.btn_macro.pack(fill="x", pady=3)

        self.btn_stop = ctk.CTkButton(
            self.bottom_btn_frame, text="Abort", font=self._font(10),
            command=self.stop_tasks, fg_color=self.theme.DANGER,
            state="disabled",
        )
        self.btn_stop.pack(fill="x", pady=3)

    # ------------------------------------------------------------------
    # Right region — preview canvas + file list + progress
    # ------------------------------------------------------------------
    def _create_right_widgets(self) -> None:
        self.right_container = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.right_container.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)

        # Preview
        self.preview_frame = ctk.CTkFrame(
            self.right_container,
            fg_color=self.theme.PANEL_BG,
            border_width=1, border_color=self.theme.BORDER,
        )
        self.preview_frame.pack(fill="both", expand=True, padx=5, pady=5)

        self.info_label = ctk.CTkLabel(
            self.preview_frame, text="Load image(s) to preview",
            font=self._font(9), text_color=self.theme.DIM_FG,
        )
        self.info_label.pack(padx=10, pady=10)

        self.canvas = ctk.CTkCanvas(self.preview_frame, bg=self.theme.CANVAS,
                                    highlightthickness=0, borderwidth=0)
        self.canvas.pack(fill="both", expand=True, padx=5, pady=5)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind("<ButtonPress-1>", self._on_guide_press)
        self.canvas.bind("<B1-Motion>", self._on_guide_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_guide_release)
        self.canvas.bind("<Motion>", self._on_guide_motion)

        # File list area
        self.asset_frame = ctk.CTkFrame(self.right_container, fg_color="transparent")
        self.asset_frame.pack(fill="x", padx=5, pady=5)

        btn_bar = ctk.CTkFrame(self.asset_frame, fg_color="transparent")
        btn_bar.pack(fill="x")
        ctk.CTkButton(btn_bar, text="+ Load", font=self._font(10),
                      command=self.select_files, fg_color=self.theme.ITEM_BG).pack(
                          side="left", expand=True, fill="x", padx=(0, 2))
        ctk.CTkButton(btn_bar, text="- Remove", font=self._font(10),
                      command=self.remove_selected, fg_color=self.theme.ITEM_BG).pack(
                          side="left", expand=True, fill="x", padx=2)
        ctk.CTkButton(btn_bar, text="Clear", font=self._font(10),
                      command=self.clear_list, fg_color=self.theme.ITEM_BG).pack(
                          side="left", expand=True, fill="x", padx=(2, 0))

        # Scrollable file list
        self.file_frame = ctk.CTkScrollableFrame(self.asset_frame, height=100,
                                                  fg_color=self.theme.PANEL_BG)
        self.file_frame.pack(fill="both", expand=True, pady=5)
        self._file_labels: List[ctk.CTkLabel] = []

        # Progress + status
        self.status_container = ctk.CTkFrame(self.right_container, fg_color="transparent")
        self.status_container.pack(side="bottom", fill="x", padx=5, pady=(0, 5))

        self.progress = ctk.CTkProgressBar(self.status_container, height=6)
        self.progress.pack(fill="x", pady=(5, 5))
        self.progress.set(0)

        self.status_label = ctk.CTkLabel(
            self.status_container, text="READY", font=self._mono(8),
            text_color=self.theme.DIM_FG,
        )
        self.status_label.pack(side="left")

    # ------------------------------------------------------------------
    # State → UI synchronisation
    # ------------------------------------------------------------------
    def _sync_ui_from_state(self) -> None:
        """Read ``self.state`` and project onto widgets (framework-agnostic)."""
        s = self.state

        # Guard: skip during early initialisation before widgets exist
        if not hasattr(self, 'template_entry'):
            return

        # Processor combo
        if s.active_processor:
            self.processor_combo.set(s.active_processor)

        # Tooltip
        self.tool_tip_label.configure(text=s.tooltip_text)

        # Template
        current = self.template_entry.get()
        if current != s.output_template:
            self.template_entry.delete(0, "end")
            self.template_entry.insert(0, s.output_template)

        # Progress
        self.progress.set(s.progress)

        # Status
        self.status_label.configure(text=s.status_text)
        if "error" in s.status_text.lower() or "fail" in s.status_text.lower():
            self.status_label.configure(text_color=self.theme.DANGER)
        elif "done" in s.status_text.lower() or "success" in s.status_text.lower():
            self.status_label.configure(text_color=self.theme.SUCCESS)
        else:
            self.status_label.configure(text_color=self.theme.DIM_FG)

        # Macro indicator
        self.macro_indicator.configure(
            text="● REC" if s.macro_recording else "○ REC",
            text_color=self.theme.DANGER if s.macro_recording else self.theme.DIM_FG,
        )

        # History
        self.history_indicator.configure(
            text=f"Hist: {self.history.undo_depth}/{self.history.redo_depth}"
        )

        # Plugin count
        self.plugin_count_label.configure(
            text=f"Ops: {s.plugin_count}"
        )

        # Preset combo
        self.preset_combo.configure(values=s.preset_names)
        if s.selected_preset:
            self.preset_combo.set(s.selected_preset)

    # ------------------------------------------------------------------
    # Processor / parameter handling
    # ------------------------------------------------------------------
    def _on_processor_changed(self, choice: str) -> None:
        for child in self.props_frame.winfo_children():
            child.destroy()
        self._param_widgets.clear()

        processor = next((p for p in ProcessorRegistry.list_all()
                          if p.display_name == choice), None)
        if not processor:
            return

        self.state.set_processor(choice, getattr(processor, 'tool_tip', ''))

        if processor.name == "custom_splitter":
            self.state.tooltip_text += (
                "  |  Drag the blue guide lines on the preview canvas to adjust their positions."
            )
            if self.thumb_img:
                self.state.status_text = "GUIDES ACTIVE — Drag lines on preview"
                self.state.status_color = self.theme.ACCENT
            self._sync_ui_from_state()
        elif self.thumb_img:
            self.state.status_text = "READY"
            self._sync_ui_from_state()

        for meta in processor.get_ui_metadata():
            frame = ctk.CTkFrame(self.props_frame, fg_color="transparent")
            frame.pack(fill="x", pady=4)
            ctk.CTkLabel(frame, text=meta["label"],
                         font=self._font(9)).pack(side="left")

            # P0-1: widget change → state.param_values → preview refresh.
            # The logic lives in the named method
            # ``_on_param_widget_changed`` (not an inline closure) so the
            # data path is deterministically testable without synthesising
            # OS-level focus/key events (which are unreliable headless).
            param_name: str = meta["name"]

            def _make_onchange(name: str):
                def _handler(*_args: object) -> None:
                    self._on_param_widget_changed(name)
                return _handler

            name, widget = create_param_widget(
                frame, meta, font=self._font(9),
                on_change=_make_onchange(param_name),
                theme=self.theme,
            )
            self._param_widgets[param_name] = widget
            widget.pack(side="right")
            self.state.param_values[name] = meta.get("default")

        self.fast_update_preview()

    def _on_param_widget_changed(self, param_name: str) -> None:
        """Synchronise one parameter widget's value into ``GuiState``.

        Reads the live widget value (``get()``) and triggers a preview
        refresh.  Called by every widget's change callback — text edits
        (``<KeyRelease>``), enum selection, and checkbox toggles.
        """
        widget = self._param_widgets.get(param_name)
        if widget is not None and hasattr(widget, "get"):
            self.state.param_values[param_name] = widget.get()
        self.fast_update_preview()

    # ------------------------------------------------------------------
    # Presets
    # ------------------------------------------------------------------
    def _refresh_preset_list(self) -> None:
        names = list_presets()
        self.state.preset_names = names
        if not names:
            self.state.selected_preset = ""
        self._sync_ui_from_state()

    def _on_preset_selected(self, choice: str) -> None:
        if not choice:
            return
        data = load_preset(choice)
        if not data:
            return
        preset_processor = data.get("processor", "")
        params = data.get("params", {})

        processor = next(
            (p for p in ProcessorRegistry.list_all()
             if p.name == preset_processor), None
        )
        if processor is None:
            messagebox.showwarning("Preset", f"Processor '{preset_processor}' not found")
            return

        if self.state.active_processor != processor.display_name:
            self._on_processor_changed(processor.display_name)

        for meta in processor.get_ui_metadata():
            key = meta["name"]
            if key in params:
                self.state.param_values[key] = params[key]
                # P1-7: Update widget display with preset values.
                w = self._param_widgets.get(key)
                if w is not None and hasattr(w, "get"):
                    ptype = meta.get("type", "str")
                    val = params[key]
                    if ptype == "bool" and hasattr(w, "_check_state"):
                        if val:
                            w.select()
                        else:
                            w.deselect()
                    elif hasattr(w, "set"):
                        w.set(str(val))
                    elif hasattr(w, "delete"):
                        try:
                            w.delete(0, "end")
                            w.insert(0, str(val))
                        except Exception:
                            pass

        self._sync_ui_from_state()
        self.fast_update_preview()

    def _save_preset(self) -> None:
        from tkinter import simpledialog
        name = simpledialog.askstring("Save Preset", "Preset name:", parent=self.root)
        if not name:
            return
        processor = next(
            (p for p in ProcessorRegistry.list_all()
             if p.display_name == self.state.active_processor), None
        )
        if not processor:
            return
        params: Dict[str, Any] = {}
        for meta in processor.get_ui_metadata():
            key = meta["name"]
            val = self.state.param_values.get(key)
            if meta.get("type") == "int":
                try:
                    params[key] = int(val) if val is not None else 0
                except (ValueError, TypeError):
                    params[key] = val
            elif meta.get("type") == "float":
                try:
                    params[key] = float(val) if val is not None else 0.0
                except (ValueError, TypeError):
                    params[key] = val
            else:
                params[key] = val
        save_preset(processor.name, name, params)
        self._refresh_preset_list()
        self.state.selected_preset = name
        self._sync_ui_from_state()

    def _delete_preset(self) -> None:
        name = self.state.selected_preset
        if not name:
            return
        if messagebox.askyesno("Delete Preset", f"Delete preset '{name}'?"):
            delete_preset(name)
            self._refresh_preset_list()

    # ------------------------------------------------------------------
    # File management
    # ------------------------------------------------------------------
    def select_files(self) -> None:
        file_types = [("Images", "*.jpg *.jpeg *.png *.bmp *.webp"), ("All Files", "*.*")]
        files = filedialog.askopenfilenames(title="Select images", filetypes=file_types)
        if files:
            self.state.current_files = list(files)
            self.state.current_file_index = 0
            self._refresh_file_list()
            self._on_file_selected(0)

    def remove_selected(self) -> None:
        idx = self.state.current_file_index
        if idx < 0 or idx >= len(self.state.current_files):
            return
        self.state.current_files.pop(idx)
        if not self.state.current_files:
            if self.thumb_img:
                self.thumb_img.close()
            self.thumb_img = None
            self.canvas.delete("all")
            self.info_label.configure(text="Load image(s) to preview")
            self.state.preview_image = None
            self.state.orig_size = (0, 0)
        else:
            self.state.current_file_index = min(idx, len(self.state.current_files) - 1)
            self._on_file_selected(self.state.current_file_index)
        self._refresh_file_list()

    def clear_list(self) -> None:
        if messagebox.askyesno("Clear", "Clear all files?"):
            self.state.clear_files()
            if self.thumb_img:
                self.thumb_img.close()
            self.thumb_img = None
            self.canvas.delete("all")
            self.info_label.configure(text="Load image(s) to preview")
            self._refresh_file_list()

    def _refresh_file_list(self) -> None:
        for lbl in self._file_labels:
            lbl.destroy()
        self._file_labels.clear()

        for i, path in enumerate(self.state.current_files):
            name = os.path.basename(path)
            is_selected = (i == self.state.current_file_index)

            lbl = ctk.CTkLabel(
                self.file_frame, text=name, anchor="w",
                font=self._font(9),
                fg_color=self.theme.SELECT if is_selected else "transparent",
                text_color=self.theme.DARK_FG if is_selected else self.theme.DIM_FG,
                corner_radius=4,
            )
            lbl.pack(fill="x", pady=1)

            idx = i  # capture
            lbl.bind("<Button-1>", lambda e, idx=idx: self._on_file_click(idx))
            self._file_labels.append(lbl)

    def _on_file_click(self, index: int) -> None:
        self.state.current_file_index = index
        self._refresh_file_list()
        self._on_file_selected(index)

    def _on_file_selected(self, index: int = 0) -> None:
        if not self.state.current_files or index >= len(self.state.current_files):
            return
        image_path = self.state.current_files[index]
        try:
            with Image.open(image_path) as img:
                self.current_orig_size = img.size
                if self.thumb_img:
                    self.thumb_img.close()
                self.thumb_img = img.convert("RGBA")
                self.thumb_img.thumbnail((1200, 1200))
                self.state.orig_size = img.size
            w, h = self.current_orig_size
            file_size = Path(image_path).stat().st_size
            size_str = f"{file_size / 1024:.1f}KB" if file_size < 1024 * 1024 else f"{file_size / (1024 * 1024):.1f}MB"
            self.info_label.configure(text=f"{w}x{h} | {size_str}")
            self._render_canvas()
        except Exception:
            logger.exception("Failed to load image: %s", image_path)
            if self.thumb_img:
                self.thumb_img.close()
            self.thumb_img = None
            self.canvas.delete("all")
            self.info_label.configure(text="Failed to load image")

    # ------------------------------------------------------------------
    # Canvas rendering (IDENTICAL to Tkinter version — CTkCanvas = tk.Canvas)
    # ------------------------------------------------------------------
    def _on_canvas_configure(self, event: Any) -> None:
        if self._resize_after_id is not None:
            self.root.after_cancel(self._resize_after_id)
        self._resize_after_id = self.root.after(50, self._debounced_render)

    def _debounced_render(self) -> None:
        """L-9: the debounced callback can fire after teardown started —
        guard against the destroyed-widget TclError."""
        self._resize_after_id = None
        try:
            if not self.root.winfo_exists():
                return
            self._render_canvas()
        except Exception:
            logger.debug("Deferred canvas render skipped", exc_info=True)

    def _render_canvas(self) -> None:
        if not self.thumb_img:
            return
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        if cw < 20 or ch < 20:
            return
        if self.current_orig_size[0] <= 0 or self.current_orig_size[1] <= 0:
            return
        self.preview_ratio = min(cw / self.current_orig_size[0], ch / self.current_orig_size[1])
        nw, nh = int(self.current_orig_size[0] * self.preview_ratio), int(self.current_orig_size[1] * self.preview_ratio)
        display_img = self.thumb_img.resize((nw, nh), Image.Resampling.BILINEAR)
        self.tk_thumb = ctk.CTkImage(light_image=display_img, size=(nw, nh))
        self.canvas.delete("all")
        self.canvas.create_image(cw // 2, ch // 2, image=self.tk_thumb, tags="bg")
        self.fast_update_preview()

    # ------------------------------------------------------------------
    # Preview overlay (IDENTICAL to Tkinter version)
    # ------------------------------------------------------------------
    def fast_update_preview(self) -> None:
        if not self.thumb_img:
            return
        self.canvas.delete("overlay")
        processor = next((p for p in ProcessorRegistry.list_all()
                          if p.display_name == self.state.active_processor), None)
        if not processor:
            return

        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        nw, nh = int(self.current_orig_size[0] * self.preview_ratio), int(self.current_orig_size[1] * self.preview_ratio)
        x0, y0 = (cw - nw) // 2, (ch - nh) // 2

        try:
            # Build a props dict compatible with draw_preview (reads .get() on values)
            props_dict: Dict[str, Any] = {}
            for key, val in self.state.param_values.items():
                props_dict[key] = val
            # draw_preview expects a dict where values are tk.Variable-like → we use raw values
            class _FakeVar:
                def __init__(self, v): self._v = v
                def get(self): return self._v
            fake_vars = {k: _FakeVar(v) for k, v in props_dict.items()}
            processor.draw_preview(
                self.canvas, thumb_size=(nw, nh), canvas_pos=(x0, y0),
                ratio=self.preview_ratio, props=fake_vars, theme=self.theme,
            )
        except Exception as e:
            logger.debug("Preview render error: %s", e)

    # ------------------------------------------------------------------
    # Guide line interaction (IDENTICAL to Tkinter version)
    # ------------------------------------------------------------------
    def _is_custom_splitter_active(self) -> bool:
        processor = next(
            (p for p in ProcessorRegistry.list_all()
             if p.display_name == self.state.active_processor), None
        )
        return processor is not None and processor.name == "custom_splitter"

    def _find_guide_at(self, x: int, y: int) -> Optional[dict]:
        hit_threshold = 14
        items = self.canvas.find_overlapping(
            x - hit_threshold, y - hit_threshold,
            x + hit_threshold, y + hit_threshold,
        )
        for item_id in items:
            tags = self.canvas.gettags(item_id)
            for tag in tags:
                if tag.startswith("guide_h_"):
                    return {"axis": "h", "index": int(tag.split("_")[-1])}
                if tag.startswith("guide_v_"):
                    return {"axis": "v", "index": int(tag.split("_")[-1])}
        return None

    def _on_guide_press(self, event: Any) -> None:
        try:
            if not self._is_custom_splitter_active():
                return
            guide = self._find_guide_at(event.x, event.y)
            if guide is not None:
                self._drag_guide = {
                    "axis": guide["axis"],
                    "index": guide["index"],
                    "start_pos": event.x if guide["axis"] == "v" else event.y,
                }
        except Exception:
            logger.debug("Guide press error", exc_info=True)

    def _on_guide_drag(self, event: Any) -> None:
        if self._drag_guide is None:
            return
        try:
            axis = self._drag_guide["axis"]
            idx = self._drag_guide["index"]
            pixel_pos = event.x if axis == "v" else event.y

            cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
            nw = int(self.current_orig_size[0] * self.preview_ratio)
            nh = int(self.current_orig_size[1] * self.preview_ratio)
            x0, y0 = (cw - nw) // 2, (ch - nh) // 2

            if axis == "v":
                new_val = int((pixel_pos - x0) / self.preview_ratio)
                new_val = max(1, min(new_val, self.current_orig_size[0] - 1))
            else:
                new_val = int((pixel_pos - y0) / self.preview_ratio)
                new_val = max(1, min(new_val, self.current_orig_size[1] - 1))

            self._enforce_guide_order(axis, idx, new_val)
            self.fast_update_preview()
        except Exception:
            logger.debug("Guide drag error", exc_info=True)

    def _on_guide_release(self, event: Any) -> None:
        self._drag_guide = None

    def _on_guide_motion(self, event: Any) -> None:
        try:
            if not self._is_custom_splitter_active():
                return
            if self._drag_guide is not None:
                return

            guide = self._find_guide_at(event.x, event.y)

            for item_id in self.canvas.find_withtag("guide_line"):
                self.canvas.itemconfigure(item_id, dash=(4, 4), width=2)

            if guide is not None:
                cursor = "sb_h_double_arrow" if guide["axis"] == "h" else "sb_v_double_arrow"
                self.canvas.configure(cursor=cursor)
                tag = f"guide_{guide['axis']}_{guide['index']}"
                for item_id in self.canvas.find_withtag(tag):
                    if "guide_handle" not in self.canvas.gettags(item_id):
                        self.canvas.itemconfigure(item_id, dash=(), width=3)
            else:
                self.canvas.configure(cursor="")
        except Exception:
            logger.debug("Guide motion error", exc_info=True)

    def _get_guide_value(self, axis: str, index: int) -> int:
        key = "h_lines" if axis == "h" else "v_lines"
        raw = self.state.param_values.get(key)
        if raw is None:
            return 0
        try:
            values = ast.literal_eval(raw) if isinstance(raw, str) else raw
            if isinstance(values, list) and index < len(values):
                return int(values[index])
        except (ValueError, SyntaxError):
            pass
        return 0

    def _set_guide_value(self, axis: str, index: int, value: int) -> None:
        key = "h_lines" if axis == "h" else "v_lines"
        raw = self.state.param_values.get(key)
        if raw is None:
            return
        try:
            values = ast.literal_eval(raw) if isinstance(raw, str) else raw
            if isinstance(values, list) and index < len(values):
                values[index] = value
                self.state.param_values[key] = str(values)
        except (ValueError, SyntaxError):
            pass

    def _enforce_guide_order(self, axis: str, index: int, value: int) -> None:
        key = "h_lines" if axis == "h" else "v_lines"
        raw = self.state.param_values.get(key)
        if raw is None:
            return
        try:
            values = ast.literal_eval(raw) if isinstance(raw, str) else raw
            if not isinstance(values, list) or index >= len(values):
                return
            if index > 0:
                prev_val = int(values[index - 1])
                if value <= prev_val:
                    value = prev_val + 1
            if index < len(values) - 1:
                next_val = int(values[index + 1])
                if value >= next_val:
                    value = next_val - 1
            if axis == "v":
                value = max(1, min(value, self.current_orig_size[0] - 2))
            else:
                value = max(1, min(value, self.current_orig_size[1] - 2))
            values[index] = value
            self.state.param_values[key] = str(values)
        except (ValueError, SyntaxError, IndexError):
            pass

    # ------------------------------------------------------------------
    # Batch processing
    # ------------------------------------------------------------------
    def run_batch(self) -> None:
        if not self.state.current_files:
            messagebox.showwarning("Warning", "No files selected")
            return
        # P1-8: Prevent concurrent batch / console / pipeline operations.
        if self._busy:
            messagebox.showwarning("Warning", "An operation is already running")
            return
        self._busy = True
        output_dir = filedialog.askdirectory(title="Select output directory")
        if not output_dir:
            # User cancelled the directory dialog — must release the busy
            # flag or the app is permanently locked ("operation running").
            self._busy = False
            return
        self._last_output_dir = output_dir

        processor = next((p for p in ProcessorRegistry.list_all()
                          if p.display_name == self.state.active_processor), None)
        if not processor:
            self._busy = False
            return

        raw_config = dict(self.state.param_values)
        try:
            processed_config = coerce_processor_config(processor, raw_config)
        except ValueError as exc:
            messagebox.showerror("Error", str(exc))
            self._busy = False
            return

        processed_config["output_dir"] = output_dir
        processed_config["template"] = self.template_entry.get()

        if self.macro.is_recording:
            self.macro.record(processor.name, dict(processed_config))

        self.btn_run.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.stop_event.clear()
        self.state.status_text = "Processing..."
        self.state.status_color = self.theme.ACCENT
        self._sync_ui_from_state()
        files = list(self.state.current_files)
        threading.Thread(
            target=self.work_thread,
            args=(processor.name, processed_config, output_dir, files),
            daemon=True,
        ).start()

    def work_thread(self, p_name: str, config: Dict[str, Any],
                    output_dir: str, files: List[str]) -> None:
        """V16: parallel batch via the shared runner (core.run_parallel_batch).

        Concurrency comes from the persisted ``max_workers`` setting
        (0 = CPU core count).  Abort semantics: pending files are
        cancelled on Stop; the file currently in flight finishes.
        Progress callbacks arrive on this worker thread and are
        marshalled to the Tk thread via ``root.after``.
        """
        from image_splitter.core import run_parallel_batch

        try:
            jobs = max(0, int(settings.get_setting("max_workers", 0) or 0))
        except (TypeError, ValueError):
            jobs = 0

        total = len(files)
        done = {"n": 0}

        def _progress(_path: str, ok: bool, msg: str) -> None:
            done["n"] += 1
            self.root.after(0, lambda d=done["n"], m=msg: self.update_progress(d / total, m))

        success_count, total_count, aborted = run_parallel_batch(
            files, p_name, config,
            jobs=jobs,
            stop_event=self.stop_event,
            on_result=_progress,
        )
        self.root.after(
            0,
            lambda: self.finish_report(success_count, total_count, aborted),
        )

    def update_progress(self, p: float, msg: str) -> None:
        self.state.set_progress(p, msg)
        self._sync_ui_from_state()

    def stop_tasks(self) -> None:
        if messagebox.askyesno("Stop", "Abort current task?"):
            self.stop_event.set()
            self.state.status_text = "Stopping..."
            self._sync_ui_from_state()

    def finish_report(self, s: int, total: int, aborted: bool = False) -> None:
        # P1-8: Clear busy flag.
        self._busy = False
        # P2-1: Check stop_event to prevent "Aborted" → "Done" race.
        if self.stop_event.is_set():
            aborted = True
        self.btn_run.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        if aborted:
            self.state.status_text = f"Aborted: {s}/{total}"
            self.state.status_color = self.theme.DANGER
        else:
            self.state.status_text = f"Done: {s}/{total}"
            self.state.status_color = self.theme.SUCCESS
            processor = next((p for p in ProcessorRegistry.list_all()
                              if p.display_name == self.state.active_processor), None)
            if processor:
                self.history.push(HistoryEntry(
                    timestamp=time.time(),
                    operator_name=processor.name,
                    config_snapshot=dict(self.state.param_values),
                    input_files=list(self.state.current_files),
                    description=f"{processor.display_name}: {s}/{total} succeeded",
                ))
        self._sync_ui_from_state()

    # ------------------------------------------------------------------
    # Pipeline panel
    # ------------------------------------------------------------------
    def _create_pipeline_panel(self) -> None:
        self.pipeline_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")

        header = ctk.CTkFrame(self.pipeline_frame, fg_color=self.theme.PANEL_BG, height=28)
        header.pack(fill="x")
        ctk.CTkLabel(header, text="Pipeline Editor (Ctrl+P to toggle)",
                     font=self._font(9), text_color=self.theme.DIM_FG).pack(side="left", padx=10)
        ctk.CTkButton(header, text="Run Chain", font=self._font(8),
                      command=self._run_pipeline_chain,
                      fg_color=self.theme.ACCENT, width=80, height=24).pack(
                          side="right", padx=(0, 8))

        self.pipeline_editor = PipelineEditor(
            self.pipeline_frame, on_change=self._on_pipeline_changed,
            font=self._mono(9),
        )
        self.pipeline_editor.pack(fill="both", expand=True)
        self.state.pipeline_visible = False

    def toggle_pipeline(self) -> None:
        if self.state.pipeline_visible:
            self.pipeline_frame.pack_forget()
        else:
            self.pipeline_frame.pack(fill="both", expand=False, padx=10, pady=(0, 6))
        self.state.toggle_pipeline()

    def _on_pipeline_changed(self) -> None:
        spec = self.pipeline_editor.to_chain_spec()
        if self.console:
            self.console.append_output(f"Chain: {spec}\n", "info")

    def _run_pipeline_chain(self) -> None:
        if not self.state.current_files:
            return
        # P1-8: Prevent concurrent operations.
        if self._busy:
            if self.console:
                self.console.append_output("[BUSY] An operation is already running\n", "warn")
            return
        self._busy = True
        spec = self.pipeline_editor.to_chain_spec()
        if not spec:
            messagebox.showwarning("Pipeline", "No steps in pipeline")
            self._busy = False
            return
        output_dir = self._last_output_dir
        files = list(self.state.current_files)
        # P1-6: Record pipeline macro step.
        if self.macro.is_recording:
            self.macro.record("pipeline_chain", {"spec": spec})
        threading.Thread(
            target=self._run_chain_thread, args=(spec, output_dir, files), daemon=True
        ).start()

    def _run_chain_thread(self, spec: str, output_dir: str, files: List[str]) -> None:
        from image_splitter.core import _prepare_image_for_save
        from image_splitter.engine.legacy_adapter import ChainAsGraph
        from image_splitter.script_engine import chain_output_spec

        # Honour a trailing format_converter in the chain (L-3): the
        # output extension and quality follow the requested format
        # instead of being hard-coded to .png.
        out_ext, save_kwargs = chain_output_spec(spec)
        ext_format = {"webp": "WEBP", "jpg": "JPEG", "jpeg": "JPEG",
                      "png": "PNG", "bmp": "BMP"}
        save_fmt = ext_format.get(out_ext, "PNG")

        for path in files:
            if self.stop_event.is_set():
                break
            try:
                with Image.open(path) as img:
                    # V14-8: preserve the source ICC profile (parity with
                    # core.process_image and ScriptEngine.chain).
                    icc_profile = img.info.get("icc_profile")
                    results = ChainAsGraph.execute_chain(img, spec)
                stem = Path(path).stem
                out = Path(output_dir)
                out.mkdir(parents=True, exist_ok=True)
                save_kwargs_file = dict(save_kwargs)
                if icc_profile:
                    save_kwargs_file["icc_profile"] = icc_profile
                for idx, res in enumerate(results, 1):
                    out_path = out / f"{stem}_chain_{idx:02d}.{out_ext}"
                    save_img = _prepare_image_for_save(res, save_fmt)
                    try:
                        save_img.save(out_path, **save_kwargs_file)
                    finally:
                        if save_img is not res:
                            save_img.close()
                    res.close()
                self.root.after(0, lambda p=path: self.console.append_output(
                    f"[OK] Chain processed: {p}\n", "success"))
            except Exception as ex:
                self.root.after(0, lambda e=ex: self.console.append_output(
                    f"[ERROR] Chain {path}: {e}\n", "error"))
        self.root.after(0, lambda: self._finish_operation())

    # ------------------------------------------------------------------
    # Console panel
    # ------------------------------------------------------------------
    def _create_console_panel(self) -> None:
        self.console_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")

        header = ctk.CTkFrame(self.console_frame, fg_color=self.theme.PANEL_BG, height=28)
        header.pack(fill="x")
        ctk.CTkLabel(header, text="Console (Ctrl+` to toggle)",
                     font=self._font(9), text_color=self.theme.DIM_FG).pack(side="left", padx=10)

        self.console = ConsolePanel(
            self.console_frame,
            script_engine=self.script_engine,
            on_execute=self._console_execute,
            on_chain=self._console_execute_chain,
            theme=self.theme,
            font=self._mono(9),
            get_current_files=lambda: list(self.state.current_files),
        )
        self.console.pack(fill="both", expand=True)
        self.console.welcome()
        self.state.console_visible = False

    def toggle_console(self) -> None:
        if self.state.console_visible:
            self.console_frame.pack_forget()
        else:
            self.console_frame.pack(fill="both", expand=False, padx=10, pady=(0, 6))
            self.console.input_entry.focus_set()
        self.state.toggle_console()

    def _console_execute(self, operator: str, config: Dict[str, Any]) -> bool:
        """Dispatch a console operator invocation.

        Returns ``False`` when the invocation was rejected (e.g. no
        files loaded) so the console can suppress the misleading
        "[OK] Dispatched" line (V16 / L-2).
        """
        if not self.state.current_files:
            self.console.append_output(
                "[INFO] No files loaded — use Load button first\n", "info")
            return False
        # P1-8: Prevent concurrent operations.
        if self._busy:
            self.console.append_output("[BUSY] An operation is already running\n", "warn")
            return False
        self._busy = True
        config["output_dir"] = self._last_output_dir
        config["template"] = self.template_entry.get()
        # P1-6: Record console macro step.
        if self.macro.is_recording:
            self.macro.record(operator, dict(config))
        files = list(self.state.current_files)

        def _work() -> None:
            from image_splitter.core import process_image
            for path in files:
                if self.stop_event.is_set():
                    break
                try:
                    process_image(path, operator, config)
                except Exception as e:
                    self.root.after(0, lambda e=e, p=path: self.console.append_output(
                        f"[ERROR] {p}: {e}\n", "error"))
            self.root.after(0, lambda: self.console.append_output(
                "[OK] Batch complete\n", "success"))
            self.root.after(0, self._finish_operation)

        threading.Thread(target=_work, daemon=True).start()
        return True

    def _console_execute_chain(self, chain_spec: str) -> None:
        """Run a console '|' chain in the background (non-blocking).

        Previously this path executed ``ScriptEngine.chain`` synchronously
        on the Tk main thread — freezing the GUI, ignoring ``_busy`` /
        ``stop_event`` / the configured output directory, and skipping
        macro recording.  It now mirrors ``_console_execute`` threading.
        """
        if not self.state.current_files:
            self.console.append_output("[INFO] No files loaded — use Load button first\n", "info")
            return
        if self._busy:
            self.console.append_output("[BUSY] An operation is already running\n", "warn")
            return
        self._busy = True
        output_dir = self._last_output_dir
        files = list(self.state.current_files)

        if self.macro.is_recording:
            self.macro.record("pipeline_chain", {"spec": chain_spec})

        def _work() -> None:
            result = self.script_engine.chain(files, chain_spec, output_dir)
            self.root.after(0, lambda: self.console.append_output(
                f"{result.message}\n", "success" if result.success else "error"))
            self.root.after(0, self._finish_operation)

        threading.Thread(target=_work, daemon=True).start()

    def _finish_operation(self) -> None:
        """P1-8: Reset busy flag after any operation completes."""
        self._busy = False

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------
    def _create_status_bar(self) -> None:
        self.status_frame = ctk.CTkFrame(self.status_container, fg_color="transparent", height=24)
        self.status_frame.pack(side="bottom", fill="x", pady=(2, 0))

        self.macro_indicator = ctk.CTkLabel(
            self.status_frame, text="○ REC", font=self._font(9),
            text_color=self.theme.DIM_FG,
        )
        self.macro_indicator.pack(side="left", padx=(2, 8))

        self.history_indicator = ctk.CTkLabel(
            self.status_frame, text="Hist: 0", font=self._font(9),
            text_color=self.theme.DIM_FG,
        )
        self.history_indicator.pack(side="left", padx=(0, 8))

        self.plugin_count_label = ctk.CTkLabel(
            self.status_frame, text=f"Ops: {len(ProcessorRegistry.list_all())}",
            font=self._font(9), text_color=self.theme.DIM_FG,
        )
        self.plugin_count_label.pack(side="right", padx=(0, 10))

    # ------------------------------------------------------------------
    # Macro / Undo / Redo
    # ------------------------------------------------------------------
    def toggle_macro_record(self) -> None:
        if self.macro.is_recording:
            script = self.macro.stop()
            if script:
                macro_dir = Path(self._last_output_dir) / "macros"
                macro_dir.mkdir(parents=True, exist_ok=True)
                ts = int(time.time())
                macro_path = macro_dir / f"macro_{ts}.py"
                try:
                    with open(macro_path, "w", encoding="utf-8") as f:
                        f.write(script)
                    self.console.append_output(f"Macro saved: {macro_path}\n", "success")
                except OSError as e:
                    self.console.append_output(f"Failed to save macro: {e}\n", "error")
        else:
            self.macro.start()
            self.console.append_output("[REC] Macro recording started\n", "info")
        self.state.macro_recording = self.macro.is_recording
        self._sync_ui_from_state()

    def undo_history(self) -> None:
        entry = self.history.undo()
        if entry:
            self.console.append_output(
                f"[UNDO] {entry.operator_name}: {entry.description}\n", "info")
            self._restore_history_entry(entry)
        else:
            self.console.append_output("[UNDO] Nothing to undo\n", "info")
            self._sync_ui_from_state()

    def redo_history(self) -> None:
        entry = self.history.redo()
        if entry:
            self.console.append_output(
                f"[REDO] {entry.operator_name}: {entry.description}\n", "info")
            self._restore_history_entry(entry)
        else:
            self.console.append_output("[REDO] Nothing to redo\n", "info")
            self._sync_ui_from_state()

    def _restore_history_entry(self, entry) -> None:
        """Restore processor selection and parameter widgets from a
        HistoryEntry config_snapshot so undo/redo actually changes the
        visible UI state, not just prints a log line."""
        # Find the historical processor
        processor = next(
            (p for p in ProcessorRegistry.list_all()
             if p.name == entry.operator_name), None)
        if processor is None:
            self.console.append_output(
                f"  (processor '{entry.operator_name}' no longer available)\n",
                "error")
            self._sync_ui_from_state()
            return

        # Switch processor if different from current (rebuilds widgets)
        current = self.state.active_processor
        if current != processor.display_name:
            self._on_processor_changed(processor.display_name)

        # Override param values and widget displays with the snapshot.
        # Pattern matches _on_preset_selected() widget-update logic.
        for meta in processor.get_ui_metadata():
            key = meta["name"]
            if key not in entry.config_snapshot:
                continue
            val = entry.config_snapshot[key]
            self.state.param_values[key] = val
            w = self._param_widgets.get(key)
            if w is not None and hasattr(w, "get"):
                ptype = meta.get("type", "str")
                if ptype == "bool" and hasattr(w, "_check_state"):
                    if val:
                        w.select()
                    else:
                        w.deselect()
                elif hasattr(w, "set"):
                    w.set(str(val))
                elif hasattr(w, "delete"):
                    try:
                        w.delete(0, "end")
                        w.insert(0, str(val))
                    except Exception:
                        pass

        self.fast_update_preview()

    # ------------------------------------------------------------------
    # Open output dir
    # ------------------------------------------------------------------
    def open_output_dir(self) -> None:
        path = self._last_output_dir
        if not os.path.exists(path):
            Path(path).mkdir(parents=True, exist_ok=True)
        try:
            if platform.system() == "Windows":
                os.startfile(path)
            elif platform.system() == "Darwin":
                subprocess.run(["open", path])
            else:
                subprocess.run(["xdg-open", path])
        except Exception as e:
            logger.error("Failed to open output dir: %s", e)
            messagebox.showwarning("Output", f"Could not open output directory: {path}")

    # ------------------------------------------------------------------
    # Keymap
    # ------------------------------------------------------------------
    def _action_handlers(self) -> Dict[str, Callable[[], None]]:
        """Map keymap action names to bound methods.

        Includes a legacy alias ``toggle_macro`` for keymaps saved by
        older versions of the app.
        """
        return {
            "run_batch": self.run_batch,
            "open_output_dir": self.open_output_dir,
            "undo_history": self.undo_history,
            "redo_history": self.redo_history,
            "toggle_macro_record": self.toggle_macro_record,
            "toggle_macro": self.toggle_macro_record,  # legacy alias
            "toggle_pipeline": self.toggle_pipeline,
            "toggle_console": self.toggle_console,
            "select_files": self.select_files,
            "remove_selected": self.remove_selected,
            "clear_list": self.clear_list,
            "stop_tasks": self.stop_tasks,
        }

    def _is_typing_context(self) -> bool:
        """Return ``True`` when keyboard focus is inside a text-input widget.

        V14-3: Tk bindtags propagate key events from the focused widget up
        to the toplevel, so a global ``<Delete>`` binding fired *in
        addition to* normal text editing (e.g. deleting the selected file
        while editing the template entry).  Keymap actions must be
        suppressed while the user is typing.
        """
        try:
            focused = self.root.focus_get()
        except Exception:
            return False
        if focused is None:
            return False
        # customtkinter wrappers (CTkComboBox hosts an inner tk.Entry, so
        # the class check alone is not enough — fall through to winfo_class).
        if isinstance(focused, (ctk.CTkEntry, ctk.CTkTextbox, ctk.CTkComboBox)):
            return True
        try:
            return focused.winfo_class() in {
                "Entry", "Text", "Spinbox", "Combobox", "TEntry", "TCombobox",
            }
        except Exception:
            return False

    def _bind_keymap(self) -> None:
        km = keymap.load_keymap()
        binds = km.get("global", {})
        handlers = self._action_handlers()
        # Introspectable dispatch table (sequence → callable).  Keeps the
        # guard path testable without synthesising OS-level key events.
        self._key_dispatches: Dict[str, Callable[[], None]] = {}
        for seq, action in binds.items():
            handler = handlers.get(action)
            if handler is not None:
                bound: Callable[[], None] = handler

                def _dispatch(_event: Any = None, h: Callable[[], None] = bound) -> None:
                    if self._is_typing_context():
                        return
                    h()
                self.root.bind(seq, _dispatch)
                self._key_dispatches[seq] = _dispatch
            else:
                logger.warning(
                    "Keymap action '%s' (%s) has no handler — "
                    "this keybinding is dead. Known actions: %s",
                    action, seq, ", ".join(sorted(handlers)),
                )

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def on_close(self) -> None:
        try:
            settings.set_setting("output_dir", self._last_output_dir)
            settings.set_setting("template", self.template_entry.get())
            # P3-8: Persist window geometry so the next session restores
            # the user's preferred size and position.
            settings.set_setting("window_geometry", self.root.geometry())
        except Exception:
            pass
        self.root.destroy()


def main() -> None:
    import argparse

    from image_splitter import __version__

    parser = argparse.ArgumentParser(
        prog="image-splitter-gui",
        description="Image Splitter Pro — GUI mode",
    )
    parser.add_argument(
        "-V", "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.parse_args()

    setup_default_logging()
    # V14: GUI users cannot see stderr — persist diagnostics to a
    # rotating file so processor failures are diagnosable after the fact.
    from image_splitter.logging_config import setup_file_logging
    setup_file_logging(level="INFO")
    root = ctk.CTk()
    app = ImageSplitterApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
