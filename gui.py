"""Graphical user interface for Image Splitter Pro."""
import logging
import os
import platform
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from image_splitter import keymap, settings
from image_splitter.core import register_all_processors, batch_process_images
from image_splitter.engine.config_coercion import coerce_processor_config
from image_splitter.engine.history import HistoryEntry, HistoryManager
from image_splitter.engine.macro import MacroRecorder
from image_splitter.engine.registry import ProcessorRegistry
from image_splitter.logging_config import setup_default_logging
from image_splitter.script_engine import ScriptEngine
from image_splitter.ui.console import ConsolePanel

logger = logging.getLogger(__name__)

_CANVAS_BG = "#0a0a0a"


def _detect_ui_font() -> str:
    """Cross-platform UI font detection."""
    system = platform.system()
    if system == "Windows":
        return "Microsoft YaHei UI"
    elif system == "Darwin":
        return "PingFang SC"
    else:
        return "Noto Sans CJK SC"


def _detect_mono_font() -> str:
    """Cross-platform monospace font detection."""
    system = platform.system()
    if system == "Windows":
        return "Consolas"
    elif system == "Darwin":
        return "Menlo"
    else:
        return "DejaVu Sans Mono"


class UITheme:
    """Theme colors for the dark UI."""
    DARK_BG = "#121212"
    PANEL_BG = "#1e1e1e"
    ITEM_BG = "#2d2d2d"
    DARK_FG = "#e0e0e0"
    DIM_FG = "#888888"
    ACCENT = "#3b82f6"
    SUCCESS = "#10b981"
    DANGER = "#ef4444"
    BORDER = "#333333"
    SELECT = "#264f78"
    CANVAS = _CANVAS_BG
    PRIMARY = ACCENT
    INFO = ACCENT


class ImageSplitterApp:
    """Main GUI application class."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Image Splitter Pro")
        self.root.geometry("1100x820")
        self.theme = UITheme()
        self.ui_font = _detect_ui_font()
        self.mono_font = _detect_mono_font()

        loaded_settings = settings.load_settings()

        self.current_files = []
        self.current_orig_size = (0, 0)
        self.thumb_img = None
        self.tk_thumb = None
        self.preview_ratio = 1.0
        self.stop_event = threading.Event()
        self.dynamic_vars = {}
        self._last_output_dir = loaded_settings.get("output_dir", "./output")

        # Blender-aligned core systems
        self.history = HistoryManager(max_depth=50)
        self.macro = MacroRecorder()
        self.script_engine = ScriptEngine()

        register_all_processors()
        self._setup_style()
        self._create_widgets()
        self._create_console_panel()
        self._create_status_bar()

    def _font(self, size: int = 10, bold: bool = False) -> Tuple[str, int, str]:
        weight = "bold" if bold else "normal"
        return (self.ui_font, size, weight)

    def _mono(self, size: int = 10) -> Tuple[str, int]:
        return (self.mono_font, size)

    def _setup_style(self) -> None:
        self.root.configure(bg=self.theme.DARK_BG)
        style = ttk.Style()
        style.theme_use('clam')

        style.configure("TFrame", background=self.theme.DARK_BG)
        style.configure("Panel.TFrame", background=self.theme.PANEL_BG)
        style.configure("TLabel", background=self.theme.PANEL_BG, foreground=self.theme.DARK_FG, font=self._font(10))
        style.configure("Caption.TLabel", background=self.theme.PANEL_BG, foreground=self.theme.ACCENT, font=self._font(11, bold=True))
        style.configure("Dim.TLabel", background=self.theme.PANEL_BG, foreground=self.theme.DIM_FG, font=self._font(9))

        style.configure("Primary.TButton", padding=8, background=self.theme.ACCENT, foreground="white", font=self._font(10, bold=True))
        style.map("Primary.TButton", background=[('active', '#2563eb'), ('disabled', '#404040')], relief=[('pressed', 'flat'), ('!pressed', 'flat')])

        style.configure("Secondary.TButton", padding=6, background=self.theme.ITEM_BG, foreground=self.theme.DARK_FG, font=self._font(10))
        style.map("Secondary.TButton", background=[('active', '#3d3d3d')])

        style.configure("Modern.Horizontal.TProgressbar", thickness=6, background=self.theme.ACCENT, troughcolor=self.theme.BORDER, borderwidth=0)

    def _create_widgets(self) -> None:
        self.main_container = tk.Frame(self.root, bg=self.theme.DARK_BG)
        self.main_container.pack(fill=tk.BOTH, expand=True)

        self.paned = ttk.PanedWindow(self.main_container, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self._create_left_panel()
        self._create_right_widgets()
        self._bind_keymap()

        processors = [p.display_name for p in ProcessorRegistry.list_all()]
        if processors:
            self.processor_combo.current(0)
            self._on_processor_changed()

    def _create_left_panel(self) -> None:
        self.left_panel = tk.Frame(self.paned, bg=self.theme.PANEL_BG, width=350)
        self.paned.add(self.left_panel, weight=0)

        self.p_inner = tk.Frame(self.left_panel, bg=self.theme.PANEL_BG, padx=20, pady=10)
        self.p_inner.pack(fill=tk.BOTH, expand=True)

        ttk.Label(self.p_inner, text="Operators", style="Caption.TLabel").pack(pady=(10, 5), anchor=tk.W)

        self.active_processor_name = tk.StringVar()
        processors = [p.display_name for p in ProcessorRegistry.list_all()]
        self.processor_combo = ttk.Combobox(self.p_inner, textvariable=self.active_processor_name,
                                            values=processors, state="readonly", font=self._font(10))
        self.processor_combo.pack(fill=tk.X, pady=(0, 5))
        self.processor_combo.bind("<<ComboboxSelected>>", self._on_processor_changed)

        self.tool_tip_var = tk.StringVar()
        self.tool_tip_label = ttk.Label(self.p_inner, textvariable=self.tool_tip_var, style="Dim.TLabel", wraplength=310)
        self.tool_tip_label.pack(anchor=tk.W, fill=tk.X, pady=(0, 15))

        tk.Frame(self.p_inner, bg=self.theme.BORDER, height=1).pack(fill=tk.X, pady=10)
        ttk.Label(self.p_inner, text="Parameters", style="Caption.TLabel").pack(pady=(10, 5), anchor=tk.W)
        self.props_frame = tk.Frame(self.p_inner, bg=self.theme.PANEL_BG)
        self.props_frame.pack(fill=tk.BOTH, expand=False, pady=5)

        tk.Frame(self.p_inner, bg=self.theme.BORDER, height=1).pack(fill=tk.X, pady=10)
        ttk.Label(self.p_inner, text="Output", style="Caption.TLabel").pack(pady=(10, 5), anchor=tk.W)
        ttk.Label(self.p_inner, text="Template:", style="Dim.TLabel").pack(anchor=tk.W)

        loaded_settings = settings.load_settings()
        default_template = loaded_settings.get("template", "{filename}_{index}")
        self.template_var = tk.StringVar(value=default_template)
        self.template_entry = tk.Entry(self.p_inner, textvariable=self.template_var,
                                       bg=self.theme.ITEM_BG, fg="white", insertbackground="white",
                                       relief="flat", font=self._mono(10))
        self.template_entry.pack(fill=tk.X, pady=(5, 2), ipady=3)
        ttk.Label(self.p_inner, text="Vars: {filename} {index} {row} {col} {w} {h} {ext} {anchor}", style="Dim.TLabel").pack(anchor=tk.W, pady=(0, 10))

        self.bottom_btn_frame = tk.Frame(self.left_panel, bg=self.theme.PANEL_BG, pady=20, padx=20)
        self.bottom_btn_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.btn_run = ttk.Button(self.bottom_btn_frame, text="Run (Ctrl+Enter)", style="Primary.TButton", command=self.run_batch)
        self.btn_run.pack(fill=tk.X, pady=5)

        self.btn_open_out = ttk.Button(self.bottom_btn_frame, text="Open Output Dir", style="Secondary.TButton", command=self.open_output_dir)
        self.btn_open_out.pack(fill=tk.X, pady=5)

        self.btn_macro = ttk.Button(self.bottom_btn_frame, text="Record Macro (Ctrl+Shift+R)", style="Secondary.TButton", command=self.toggle_macro_record)
        self.btn_macro.pack(fill=tk.X, pady=5)

        self.btn_stop = ttk.Button(self.bottom_btn_frame, text="Abort", state=tk.DISABLED, command=self.stop_tasks)
        self.btn_stop.pack(fill=tk.X, pady=5)

    def _bind_keymap(self) -> None:
        loaded_keymap = keymap.load_keymap()
        global_binds = loaded_keymap.get("global", {})
        for key_seq, action in global_binds.items():
            handler = self._resolve_action(action)
            if handler:
                try:
                    self.root.bind(key_seq, lambda e, h=handler: h())
                except tk.TclError:
                    logger.warning("Invalid key sequence: %s", key_seq)

        self.file_listbox.bind("<Delete>", lambda e: self.remove_selected())
        self.root.bind("<Control-grave>", lambda e: self.toggle_console())
        self.root.bind("<Control-Shift-R>", lambda e: self.toggle_macro_record())
        self.root.bind("<Control-z>", lambda e: self.undo_history())
        self.root.bind("<Control-Shift-Z>", lambda e: self.redo_history())

    def _resolve_action(self, action_name: str) -> Optional[Callable]:
        return {
            "select_files": self.select_files,
            "run_batch": self.run_batch,
            "remove_selected": self.remove_selected,
            "open_output_dir": self.open_output_dir,
            "stop_tasks": self.stop_tasks,
            "toggle_console": self.toggle_console,
            "toggle_macro": self.toggle_macro_record,
        }.get(action_name)

    def _create_right_widgets(self) -> None:
        self.right_container = tk.Frame(self.paned, bg=self.theme.DARK_BG)
        self.paned.add(self.right_container, weight=1)

        self.preview_frame = tk.Frame(self.right_container, bg=self.theme.PANEL_BG, bd=1, highlightbackground=self.theme.BORDER, highlightthickness=1)
        self.preview_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)

        self.info_label = tk.Label(self.preview_frame, text="Load image(s) to preview", bg=self.theme.PANEL_BG, fg=self.theme.DIM_FG, font=self._font(9))
        self.info_label.pack(pady=10)

        self.canvas = tk.Canvas(self.preview_frame, bg=self.theme.CANVAS, highlightthickness=0, borderwidth=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        self.asset_frame = tk.Frame(self.right_container, bg=self.theme.DARK_BG)
        self.asset_frame.pack(fill=tk.X, padx=15, pady=10)

        self.asset_btn_frame = tk.Frame(self.asset_frame, bg=self.theme.DARK_BG)
        self.asset_btn_frame.pack(fill=tk.X)
        ttk.Button(self.asset_btn_frame, text="+ Load", style="Secondary.TButton", command=self.select_files).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 2))
        ttk.Button(self.asset_btn_frame, text="- Remove", style="Secondary.TButton", command=self.remove_selected).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        ttk.Button(self.asset_btn_frame, text="Clear", style="Secondary.TButton", command=self.clear_list).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2, 0))

        self.file_listbox = tk.Listbox(self.asset_frame, bg=self.theme.PANEL_BG, fg=self.theme.DARK_FG,
                                       borderwidth=0, height=6, selectbackground=self.theme.SELECT,
                                       font=self._mono(9), highlightthickness=1, highlightcolor=self.theme.ACCENT,
                                       selectmode=tk.EXTENDED)
        self.file_listbox.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=5)
        self.file_listbox.bind("<<ListboxSelect>>", self._on_file_selected)
        self.file_listbox.bind("<Delete>", lambda e: self.remove_selected())

        self.status_container = tk.Frame(self.right_container, bg=self.theme.DARK_BG)
        self.status_container.pack(side=tk.BOTTOM, fill=tk.X, padx=15, pady=(0, 10))
        self.progress_var = tk.DoubleVar()
        self.progress = ttk.Progressbar(self.status_container, length=100, mode='determinate', variable=self.progress_var, style="Modern.Horizontal.TProgressbar")
        self.progress.pack(fill=tk.X, pady=(5, 5))
        self.status_label = tk.Label(self.status_container, text="READY", font=self._mono(8), bg=self.theme.DARK_BG, fg=self.theme.DIM_FG)
        self.status_label.pack(side=tk.LEFT)

    def _on_processor_changed(self, event: Optional[tk.Event] = None) -> None:
        for child in self.props_frame.winfo_children():
            child.destroy()
        self.dynamic_vars = {}

        display_name = self.active_processor_name.get()
        processor = next((p for p in ProcessorRegistry.list_all() if p.display_name == display_name), None)
        if not processor:
            return

        self.tool_tip_var.set(getattr(processor, 'tool_tip', ''))

        for meta in processor.get_ui_metadata():
            frame = tk.Frame(self.props_frame, bg=self.theme.PANEL_BG)
            frame.pack(fill=tk.X, pady=4)
            tk.Label(frame, text=meta["label"], bg=self.theme.PANEL_BG, font=self._font(9)).pack(side=tk.LEFT)

            p_type = meta.get("type", "str")
            if p_type == "bool":
                var = tk.BooleanVar(value=bool(meta["default"]))
                self.dynamic_vars[meta["name"]] = var
                tk.Checkbutton(frame, variable=var, bg=self.theme.PANEL_BG, activebackground=self.theme.PANEL_BG,
                               command=self.fast_update_preview, selectcolor=self.theme.DARK_BG).pack(side=tk.RIGHT)
            elif p_type == "enum":
                var = tk.StringVar(value=str(meta["default"]))
                self.dynamic_vars[meta["name"]] = var
                cb = ttk.Combobox(frame, textvariable=var, values=meta.get("options", []), state="readonly", font=self._font(9), width=12)
                cb.pack(side=tk.RIGHT)
                cb.bind("<<ComboboxSelected>>", lambda e: self.fast_update_preview())
            else:
                var = tk.StringVar(value=str(meta["default"]))
                self.dynamic_vars[meta["name"]] = var
                entry = tk.Entry(frame, textvariable=var, bg=self.theme.ITEM_BG, fg="white", width=12, insertbackground="white", relief="flat")
                entry.pack(side=tk.RIGHT, ipady=2)
                entry.bind("<KeyRelease>", lambda e: self.fast_update_preview())

        self.fast_update_preview()

    def select_files(self) -> None:
        file_types = [("Images", "*.jpg *.jpeg *.png *.bmp *.webp"), ("All Files", "*.*")]
        files = filedialog.askopenfilenames(title="Select images", filetypes=file_types)
        if files:
            self.current_files = list(files)
            self.file_listbox.delete(0, tk.END)
            for f in self.current_files:
                self.file_listbox.insert(tk.END, os.path.basename(f))
            self.file_listbox.selection_set(0)
            self._on_file_selected()

    def remove_selected(self) -> None:
        indices = sorted(self.file_listbox.curselection(), reverse=True)
        if not indices:
            return
        for i in indices:
            self.file_listbox.delete(i)
            self.current_files.pop(i)
        if not self.current_files:
            self.thumb_img = None
            self.canvas.delete("all")
            self.info_label.config(text="Load image(s) to preview")
        else:
            self.file_listbox.selection_set(0)
            self._on_file_selected()

    def clear_list(self) -> None:
        if messagebox.askyesno("Clear", "Clear all files?"):
            self.file_listbox.delete(0, tk.END)
            self.current_files = []
            self.thumb_img = None
            self.canvas.delete("all")
            self.info_label.config(text="Load image(s) to preview")

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
            messagebox.showinfo("Info", f"Output: {path}")

    def run_batch(self) -> None:
        if not self.current_files:
            messagebox.showwarning("Warning", "No files selected")
            return
        output_dir = filedialog.askdirectory(title="Select output directory")
        if not output_dir:
            return
        self._last_output_dir = output_dir

        display_name = self.active_processor_name.get()
        processor = next((p for p in ProcessorRegistry.list_all() if p.display_name == display_name), None)
        if not processor:
            return

        raw_config = {meta["name"]: self.dynamic_vars[meta["name"]].get() for meta in processor.get_ui_metadata()}
        try:
            processed_config = coerce_processor_config(processor, raw_config)
        except ValueError as exc:
            messagebox.showerror("Error", str(exc))
            return

        processed_config["output_dir"] = output_dir
        processed_config["template"] = self.template_var.get()

        # Macro recording
        if self.macro.is_recording:
            self.macro.record(processor.name, dict(processed_config))

        self.btn_run.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.stop_event.clear()
        self.status_label.config(text="Processing...", foreground=self.theme.ACCENT)
        threading.Thread(target=self.work_thread, args=(processor.name, processed_config, output_dir), daemon=True).start()

    def work_thread(self, p_name: str, config: Dict[str, Any], output_dir: str) -> None:
        total = len(self.current_files)
        success_count = 0
        for i, (path, is_success, msg) in enumerate(batch_process_images(self.current_files, p_name, config)):
            if self.stop_event.is_set():
                self.root.after(0, lambda: self.finish_report(success_count, total, True))
                return
            if is_success:
                success_count += 1
            progress = (i + 1) / total * 100
            self.root.after(0, lambda p=progress, m=msg: self.update_progress(p, m))
        self.root.after(0, lambda: self.finish_report(success_count, total))

    def update_progress(self, p: float, msg: str) -> None:
        self.progress_var.set(p)
        self.status_label.config(text=msg)

    def stop_tasks(self) -> None:
        if messagebox.askyesno("Stop", "Abort current task?"):
            self.stop_event.set()
            self.status_label.config(text="Stopping...")

    def fast_update_preview(self) -> None:
        if not self.thumb_img:
            return
        self.canvas.delete("overlay")
        display_name = self.active_processor_name.get()
        processor = next((p for p in ProcessorRegistry.list_all() if p.display_name == display_name), None)
        if not processor:
            return

        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        nw, nh = int(self.current_orig_size[0] * self.preview_ratio), int(self.current_orig_size[1] * self.preview_ratio)
        x0, y0 = (cw - nw) // 2, (ch - nh) // 2

        try:
            processor.draw_preview(
                self.canvas, thumb_size=(nw, nh), canvas_pos=(x0, y0),
                ratio=self.preview_ratio, props=self.dynamic_vars, theme=self.theme,
            )
        except Exception as e:
            logger.debug("Preview render error: %s", e)

    def _on_file_selected(self, event: Optional[tk.Event] = None) -> None:
        selection = self.file_listbox.curselection()
        if not selection:
            return
        image_path = self.current_files[selection[0]]
        try:
            with Image.open(image_path) as img:
                self.current_orig_size = img.size
                thumb = img.convert("RGBA")
                thumb.thumbnail((1200, 1200))
                self.thumb_img = thumb
            w, h = self.current_orig_size
            file_size = Path(image_path).stat().st_size
            size_str = f"{file_size / 1024:.1f}KB" if file_size < 1024 * 1024 else f"{file_size / (1024 * 1024):.1f}MB"
            self.info_label.config(text=f"{w}x{h} | {size_str}")
            self._render_canvas()
        except Exception:
            self.thumb_img = None
            self.canvas.delete("all")
            self.info_label.config(text="Failed to load image")

    def _on_canvas_configure(self, event: tk.Event) -> None:
        self.root.after(50, self._render_canvas)

    def _render_canvas(self) -> None:
        if not self.thumb_img:
            return
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        if cw < 20 or ch < 20:
            return
        self.preview_ratio = min(cw / self.current_orig_size[0], ch / self.current_orig_size[1])
        nw, nh = int(self.current_orig_size[0] * self.preview_ratio), int(self.current_orig_size[1] * self.preview_ratio)
        display_img = self.thumb_img.resize((nw, nh), Image.Resampling.BILINEAR)
        self.tk_thumb = ImageTk.PhotoImage(display_img)
        self.canvas.delete("all")
        self.canvas.create_image(cw // 2, ch // 2, image=self.tk_thumb, tags="bg")
        self.fast_update_preview()

    def finish_report(self, s: int, total: int, aborted: bool = False) -> None:
        self.btn_run.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        if aborted:
            self.status_label.config(text=f"Aborted: {s}/{total}", foreground=self.theme.DANGER)
        else:
            self.status_label.config(text=f"Done: {s}/{total}", foreground=self.theme.SUCCESS)
            display_name = self.active_processor_name.get()
            processor = next((p for p in ProcessorRegistry.list_all()
                              if p.display_name == display_name), None)
            if processor:
                raw_config = {meta["name"]: self.dynamic_vars[meta["name"]].get()
                              for meta in processor.get_ui_metadata()}
                self.history.push(HistoryEntry(
                    timestamp=time.time(),
                    operator_name=processor.name,
                    config_snapshot=dict(raw_config),
                    input_files=list(self.current_files),
                    description=f"{processor.display_name}: {s}/{total} succeeded",
                ))
        self._update_status_indicators()

    def on_close(self) -> None:
        if self.btn_run['state'] == tk.DISABLED:
            if not messagebox.askyesno("Exit", "Task is running. Force quit?"):
                return
            self.stop_event.set()
        try:
            settings.set_setting("output_dir", self._last_output_dir)
            settings.set_setting("template", self.template_var.get())
        except Exception:
            pass
        self.root.destroy()

    # ----------------------------------------------------------------
    # Console panel
    # ----------------------------------------------------------------
    def _create_console_panel(self) -> None:
        self.console_frame = tk.Frame(self.main_container, bg=self.theme.DARK_BG)

        console_header = tk.Frame(self.console_frame, bg=self.theme.PANEL_BG, height=28)
        console_header.pack(fill=tk.X)
        tk.Label(
            console_header, text="Console (Ctrl+` to toggle)",
            bg=self.theme.PANEL_BG, fg=self.theme.DIM_FG, font=self._font(9)
        ).pack(side=tk.LEFT, padx=10)

        self.console = ConsolePanel(
            self.console_frame,
            script_engine=self.script_engine,
            on_execute=self._console_execute,
            theme=self.theme,
            font=self._mono(9),
        )
        self.console.pack(fill=tk.BOTH, expand=True)
        self.console.welcome()
        self.console_frame.pack_forget()
        self._console_visible = False

    def toggle_console(self) -> None:
        if self._console_visible:
            self.console_frame.pack_forget()
            self._console_visible = False
        else:
            self.console_frame.pack(fill=tk.BOTH, expand=False, padx=10, pady=(0, 6))
            self._console_visible = True
            self.console.input_entry.focus_set()

    def _console_execute(self, operator: str, config: Dict[str, Any]) -> None:
        if self.current_files:
            config["output_dir"] = self._last_output_dir
            config["template"] = self.template_var.get()
            for path in self.current_files:
                from image_splitter.core import process_image
                process_image(path, operator, config)

    # ----------------------------------------------------------------
    # Status bar
    # ----------------------------------------------------------------
    def _create_status_bar(self) -> None:
        self.status_frame = tk.Frame(
            self.status_container, bg=self.theme.DARK_BG, height=24
        )
        self.status_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(2, 0))

        self.macro_indicator = tk.Label(
            self.status_frame,
            text="● REC" if self.macro.is_recording else "○ REC",
            font=self._font(9),
            bg=self.theme.DARK_BG,
            fg=self.theme.DANGER if self.macro.is_recording else self.theme.DIM_FG,
        )
        self.macro_indicator.pack(side=tk.LEFT, padx=(2, 8))

        self.history_indicator = tk.Label(
            self.status_frame,
            text=f"Hist: {self.history.undo_depth}",
            font=self._font(9),
            bg=self.theme.DARK_BG,
            fg=self.theme.DIM_FG,
        )
        self.history_indicator.pack(side=tk.LEFT, padx=(0, 8))

        self.plugin_count_label = tk.Label(
            self.status_frame,
            text=f"Ops: {len(ProcessorRegistry.list_all())}",
            font=self._font(9),
            bg=self.theme.DARK_BG,
            fg=self.theme.DIM_FG,
        )
        self.plugin_count_label.pack(side=tk.RIGHT, padx=(0, 10))

    def _update_status_indicators(self) -> None:
        self.macro_indicator.config(
            text="● REC" if self.macro.is_recording else "○ REC",
            fg=self.theme.DANGER if self.macro.is_recording else self.theme.DIM_FG,
        )
        self.history_indicator.config(
            text=f"Hist: {self.history.undo_depth}/{self.history.redo_depth}"
        )

    # ----------------------------------------------------------------
    # Macro recording
    # ----------------------------------------------------------------
    def toggle_macro_record(self) -> None:
        if self.macro.is_recording:
            script = self.macro.stop()
            if script:
                macro_dir = Path(self._last_output_dir) / "macros"
                macro_dir.mkdir(parents=True, exist_ok=True)
                ts = int(time.time())
                macro_path = macro_dir / f"macro_{ts}.py"
                with open(macro_path, "w", encoding="utf-8") as f:
                    f.write(script)
                self.console.append_output(
                    f"Macro saved: {macro_path}\n", "success"
                )
        else:
            self.macro.start()
            self.console.append_output("[REC] Macro recording started\n", "info")
        self._update_status_indicators()

    # ----------------------------------------------------------------
    # Undo / Redo
    # ----------------------------------------------------------------
    def undo_history(self) -> None:
        entry = self.history.undo()
        if entry:
            self.console.append_output(
                f"[UNDO] {entry.operator_name}: {entry.description}\n", "info"
            )
        else:
            self.console.append_output("[UNDO] Nothing to undo\n", "info")
        self._update_status_indicators()

    def redo_history(self) -> None:
        entry = self.history.redo()
        if entry:
            self.console.append_output(
                f"[REDO] {entry.operator_name}: {entry.description}\n", "info"
            )
        else:
            self.console.append_output("[REDO] Nothing to redo\n", "info")
        self._update_status_indicators()


def main() -> None:
    setup_default_logging()
    root = tk.Tk()
    app = ImageSplitterApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
