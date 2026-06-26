"""Auto-generate UI metadata from dataclass field annotations.

Provides :func:`ui_metadata_from_dataclass` — the single source of truth
for the processor parameter schema consumed by CLI (``--set`` coercion),
GUI auto-layout, and the ``config_coercion`` module.  Each dataclass
``field(metadata={...})`` carries:

    ``label`` (str)    — Human-readable label for UI display.
    ``options`` (list) — Enum choices (forces ``type="enum"``).
    ``min`` / ``max``  — Numeric bounds (optional).

Base types are inferred from Python type annotations (int→"int",
float→"float", bool→"bool", str→"str", list/tuple→"list").
"""

from __future__ import annotations

import typing
from dataclasses import MISSING, Field, fields
from typing import Any


# Maps Python types (and their origins) to UI metadata type strings.
_TYPE_MAP: dict[type[object], str] = {
    int: "int",
    float: "float",
    bool: "bool",
    str: "str",
    list: "list",
    tuple: "list",
}


def _resolve_python_type(field_type: Any) -> Any:
    """Resolve the concrete Python type from a field annotation.

    Handles ``Optional[X]`` → ``X``, ``Union[X, None]`` → ``X``,
    and generic origins (``List[int]`` → ``list``, ``Tuple[...]`` → ``tuple``).

    Returns a type suitable as a key in ``_TYPE_MAP``, or ``str`` as fallback.
    """
    origin = typing.get_origin(field_type)
    if origin is not None:
        if origin is typing.Union:
            args = [a for a in typing.get_args(field_type) if a is not type(None)]
            if len(args) == 1:
                return _resolve_python_type(args[0])
            return str
        if origin in _TYPE_MAP:
            return origin
        return str
    if field_type in _TYPE_MAP:
        return field_type
    return str


def ui_metadata_from_dataclass(dc_class: type[Any]) -> list[dict[str, Any]]:
    """Generate the UI metadata list from a dataclass's field definitions.

    Each dataclass :class:`Field` whose ``metadata`` dict contains a
    ``"label"`` key is included in the output.  Fields without a label
    (internal / shared helpers like ``output_dir`` or ``template``) are
    skipped so that only processor-specific parameters appear in the UI.

    The ``metadata`` dict may also contain:

    * ``options`` — a list of string choices → ``type`` becomes ``"enum"``.
    * ``min`` / ``max`` — numeric bounds forwarded to the UI.

    Returns:
        A list of metadata dicts in the format expected by
        ``config_coercion.coerce_processor_config()`` and the GUI.
    """
    result: list[dict[str, Any]] = []

    for f in fields(dc_class):
        if f.name.startswith("_"):
            continue

        fm: dict[str, Any] = dict(f.metadata) if f.metadata else {}
        label = fm.get("label")
        if label is None:
            continue  # field not exposed to UI

        options: list[str] | None = fm.get("options")

        # Resolve the UI type string.
        if options:
            ui_type = "enum"
        else:
            python_type = _resolve_python_type(f.type)
            ui_type = _TYPE_MAP.get(python_type, "str")

        # Default value (MISSING for required fields and default_factory).
        if f.default is not MISSING:
            default = f.default
        elif f.default_factory is not MISSING:
            try:
                default = f.default_factory()
            except Exception:
                default = None
        else:
            default = None

        entry: dict[str, Any] = {
            "name": f.name,
            "label": label,
            "type": ui_type,
            "default": default,
        }
        if options:
            entry["options"] = options
        if fm.get("min") is not None:
            entry["min"] = fm["min"]
        if fm.get("max") is not None:
            entry["max"] = fm["max"]

        result.append(entry)

    return result
