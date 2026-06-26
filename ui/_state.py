"""GUI state layer — framework-agnostic ViewModel for Image Splitter Pro.

Design principle:
    Widget callbacks update **state**.
    ``_sync_ui_from_state()`` reads state and projects it onto widgets.
    Business logic reads from state, never from widget variables.

This decoupling means:
    - Today: customtkinter reads ``state`` and renders ``CTk*`` widgets.
    - Tomorrow: Dear PyGui reads the same ``state`` and renders via immediate mode.
    - The ``engine/``, ``core.py``, and all processor logic are untouched.

Usage in gui.py:
    self.state = GuiState()
    self.state.active_processor = "grid_splitter"
    self._sync_ui_from_state()  # updates combobox, params, preview
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from PIL import Image


@dataclass
class GuiState:
    """All observable GUI state as plain Python values.

    No tkinter types allowed here — this is the pure data layer
    that survives framework migrations.

    Widget variable equivalents (for migration reference):
        active_processor      ← self.active_processor_name (StringVar)
        tooltip_text          ← self.tool_tip_var (StringVar)
        selected_preset       ← self.preset_var (StringVar)
        output_template       ← self.template_var (StringVar)
        param_values          ← self.dynamic_vars (Dict[str, Variable])
        progress              ← self.progress_var (DoubleVar)
    """

    # ── Processor state ───────────────────────────────────────────────
    active_processor: str = ""  # display_name of selected processor
    tooltip_text: str = ""  # processor tooltip / hint text
    param_values: Dict[str, Any] = field(default_factory=dict)
    output_template: str = "{filename}_{index}"
    output_dir: str = "./output"

    # ── Preset state ──────────────────────────────────────────────────
    selected_preset: str = ""
    preset_names: List[str] = field(default_factory=list)

    # ── File / asset state ────────────────────────────────────────────
    current_files: List[str] = field(default_factory=list)
    current_file_index: int = 0  # selected index in file listbox

    # ── Preview state ─────────────────────────────────────────────────
    preview_image: Optional[Image.Image] = None  # PIL thumbnail
    orig_size: Tuple[int, int] = (0, 0)
    preview_ratio: float = 1.0  # orig → preview scale factor
    guide_drag: Optional[dict] = None  # {axis, index, start_pos}

    # ── Progress / status ─────────────────────────────────────────────
    progress: float = 0.0  # 0.0 – 1.0
    status_text: str = "READY"
    status_color: str = "#888888"  # DIM_FG by default

    # ── Panel visibility ──────────────────────────────────────────────
    pipeline_visible: bool = False
    console_visible: bool = False

    # ── Macro ─────────────────────────────────────────────────────────
    macro_recording: bool = False
    history_depth: int = 0

    # ── Plugin count (status bar) ─────────────────────────────────────
    plugin_count: int = 0

    # ── Abort flag (cross-thread) ─────────────────────────────────────
    # NOTE: threading.Event must be separate from this dataclass
    # because it is not serialisable / observable.  The app instance
    # owns it directly: ``self.stop_event = threading.Event()``.

    # ── Callbacks (injected by the View layer) ────────────────────────
    # These are NOT serialisable state — they are wiring between
    # the ViewModel and the View.  Set by gui.py after construction.
    on_state_changed: Optional[Callable[[], None]] = field(
        default=None, repr=False, compare=False
    )

    # ── Convenience helpers ───────────────────────────────────────────

    def get_param(self, key: str, default: Any = None) -> Any:
        """Get a parameter value with fallback."""
        return self.param_values.get(key, default)

    def set_param(self, key: str, value: Any) -> None:
        """Set a parameter value and notify the View."""
        self.param_values[key] = value
        self._notify()

    def set_params_bulk(self, mapping: Dict[str, Any]) -> None:
        """Set multiple parameters at once (single notification)."""
        self.param_values.update(mapping)
        self._notify()

    def set_processor(self, display_name: str, tooltip: str = "") -> None:
        """Switch active processor and clear old parameter values."""
        self.active_processor = display_name
        self.tooltip_text = tooltip
        self.param_values.clear()
        self._notify()

    def select_file(self, index: int) -> None:
        """Change the selected file index."""
        self.current_file_index = max(0, min(index, len(self.current_files) - 1))
        self._notify()

    def clear_files(self) -> None:
        """Remove all files and reset preview."""
        self.current_files.clear()
        self.current_file_index = 0
        self.preview_image = None
        self.orig_size = (0, 0)
        self.preview_ratio = 1.0
        self._notify()

    def set_progress(self, value: float, status: str = "") -> None:
        """Update progress bar and optional status text."""
        self.progress = max(0.0, min(1.0, value))
        if status:
            self.status_text = status
        self._notify()

    def toggle_pipeline(self) -> None:
        self.pipeline_visible = not self.pipeline_visible
        self._notify()

    def toggle_console(self) -> None:
        self.console_visible = not self.console_visible
        self._notify()

    def _notify(self) -> None:
        """Notify the View that state changed (triggers re-render)."""
        if self.on_state_changed is not None:
            self.on_state_changed()
