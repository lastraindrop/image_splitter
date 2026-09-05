"""Shared parameter widget factory.

Provides :func:`create_param_widget` to build customtkinter widgets from
processor UI metadata dicts, eliminating duplicated if-elif-else
branching in gui.py and pipeline.py.

Framework-agnostic design:
    Returns ``(param_name, widget)`` tuples.  The caller reads values
    via ``widget.get()`` and writes defaults via ``widget.set()``.
    No ``tk.Variable`` coupling — ready for Dear PyGui migration.
"""

from typing import Any, Callable, Dict, Optional, Tuple

import customtkinter as ctk


def create_param_widget(
    parent: Any,
    meta: Dict[str, Any],
    *,
    value: Any = None,
    font: Tuple = ("Consolas", 9),
    on_change: Optional[Callable[[], None]] = None,
    theme: Optional[Any] = None,
) -> Tuple[str, Any]:
    """Create a widget for a single parameter, driven by its UI metadata.

    Args:
        parent: Parent customtkinter widget.
        meta: UI metadata dict from ``processor.get_ui_metadata()``
            (must have ``name``, ``type``, ``default`` keys).
        value: Current value to pre-fill.  Falls back to ``meta["default"]``.
        font: Font tuple ``(family, size)``.
        on_change: Callback invoked when the widget value changes.
        theme: Optional theme object (unused — ctk handles theming natively).

    Returns:
        ``(param_name, widget)`` tuple.  Call ``widget.get()`` to read,
        ``widget.set(value)`` to write.
    """
    p_type = meta.get("type", "str")
    param_name: str = meta["name"]
    default = meta.get("default")

    if value is not None:
        initial = value
    elif default is not None:
        initial = default
    else:
        initial = ""

    widget: Any

    if p_type == "bool":
        widget = ctk.CTkCheckBox(
            parent,
            text="",
            width=24,
            command=on_change if on_change else None,
        )
        widget._check_state = bool(initial)
        if bool(initial):
            widget.select()
        else:
            widget.deselect()

    elif p_type == "enum":
        widget = ctk.CTkComboBox(
            parent,
            values=meta.get("options", []),
            command=lambda _: on_change() if on_change else None,
            font=font,
            width=140,
        )
        widget.set(str(initial))

    else:
        widget = ctk.CTkEntry(
            parent,
            font=font,
            width=140,
        )
        widget.insert(0, str(initial))
        if on_change is not None:
            widget.bind("<KeyRelease>", lambda e: on_change())

    return param_name, widget
