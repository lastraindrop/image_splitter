"""Parameter presets system for save/load/apply processor configurations.

Stores named presets as JSON files in ~/.image_splitter/presets/.
Each preset captures a processor's full parameter set for easy recall.
"""
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from image_splitter.settings import get_config_dir

PRESETS_DIR_NAME = "presets"

# Windows-illegal filename characters (also strip control chars).
_ILLEGAL_NAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _presets_dir() -> Path:
    d = get_config_dir() / PRESETS_DIR_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def _preset_path(name: str) -> Path:
    """Map a preset name to a safe filesystem path.

    V14-9: full sanitization — a name containing e.g. a colon ("a:b")
    previously raised an unhandled OSError on Windows when the file was
    opened for writing.
    """
    safe = _ILLEGAL_NAME_CHARS.sub("_", name)
    safe = safe.strip(" .")  # Windows rejects trailing dots/spaces
    if not safe or not any(c.isalnum() for c in safe):
        safe = "unnamed"
    return _presets_dir() / f"{safe}.json"


def save_preset(processor_name: str, name: str, params: Dict[str, Any]) -> Path:
    """Save a named preset for a processor.

    Args:
        processor_name: Name of the processor (e.g. 'grid_splitter').
        name: Human-readable preset name.
        params: Dictionary of parameter name → value.

    Returns:
        Path to the saved preset file.

    Raises:
        OSError: If the file cannot be written.
    """
    data: Dict[str, Any] = {
        "name": name,
        "processor": processor_name,
        "params": params,
    }
    path = _preset_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return path


def load_preset(name: str) -> Optional[Dict[str, Any]]:
    """Load a named preset.

    Args:
        name: Preset name.

    Returns:
        Dict with 'processor' and 'params' keys, or None if not found.
    """
    path = _preset_path(name)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def list_presets() -> List[str]:
    """List all saved preset names.

    Returns:
        Sorted list of preset names (without extension).
    """
    names = []
    for p in _presets_dir().glob("*.json"):
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            names.append(data.get("name", p.stem))
        except (json.JSONDecodeError, IOError):
            names.append(p.stem)
    return sorted(names)


def delete_preset(name: str) -> bool:
    """Delete a named preset.

    Args:
        name: Preset name to delete.

    Returns:
        True if deleted, False if not found.
    """
    path = _preset_path(name)
    if path.exists():
        path.unlink()
        return True
    return False


def export_preset(name: str, output_path: str) -> bool:
    """Export a preset to an external JSON file.

    Args:
        name: Preset name.
        output_path: Path to write the preset JSON.

    Returns:
        True if exported, False if preset not found or write fails.
    """
    data = load_preset(name)
    if data is None:
        return False
    out = Path(output_path)
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except (IOError, OSError) as e:
        import logging
        logging.getLogger(__name__).warning("Failed to export preset: %s", e)
        return False


def import_preset(file_path: str) -> Optional[str]:
    """Import a preset from an external JSON file.

    Args:
        file_path: Path to a preset JSON file.

    Returns:
        The imported preset name, or None on failure.
    """
    p = Path(file_path)
    if not p.exists():
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return None

    name = data.get("name", p.stem)
    processor = data.get("processor", "")
    params = data.get("params", {})

    if not name or not processor:
        return None

    # V15: save_preset raises OSError on unwritable preset dirs —
    # surface it as a failed import instead of crashing the caller.
    try:
        save_preset(processor, name, params)
    except (IOError, OSError):
        return None
    return name
