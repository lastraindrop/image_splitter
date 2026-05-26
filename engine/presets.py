"""Parameter presets system for save/load/apply processor configurations.

Stores named presets as JSON files in ~/.image_splitter/presets/.
Each preset captures a processor's full parameter set for easy recall.
"""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from image_splitter.settings import get_config_dir

PRESETS_DIR_NAME = "presets"


def _presets_dir() -> Path:
    d = get_config_dir() / PRESETS_DIR_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def _preset_path(name: str) -> Path:
    safe = name.replace("/", "_").replace("\\", "_").replace("..", "_")
    return _presets_dir() / f"{safe}.json"


def save_preset(processor_name: str, name: str, params: Dict[str, Any]) -> Path:
    """Save a named preset for a processor.

    Args:
        processor_name: Name of the processor (e.g. 'grid_splitter').
        name: Human-readable preset name.
        params: Dictionary of parameter name → value.

    Returns:
        Path to the saved preset file.
    """
    data: Dict[str, Any] = {
        "name": name,
        "processor": processor_name,
        "params": params,
    }
    path = _preset_path(name)
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
        True if exported, False if preset not found.
    """
    data = load_preset(name)
    if data is None:
        return False
    out = Path(output_path)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return True


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

    save_preset(processor, name, params)
    return name
