# image_splitter/settings.py
"""Settings system for CLI configuration persistence."""
import json
from pathlib import Path
from typing import Any, Dict

DEFAULT_SETTINGS: Dict[str, Any] = {
    "output_dir": "./output",
    "default_processor": "grid_splitter",
    "template": "{filename}_{index}",
    "max_workers": 0,
    "default_rows": 3,
    "default_cols": 3,
}


def get_config_dir() -> Path:
    """Get config directory path (~/.image_splitter/)."""
    home = Path.home()
    config_dir = home / ".image_splitter"
    config_dir.mkdir(exist_ok=True)
    return config_dir


def get_settings_path() -> Path:
    """Get settings file path."""
    return get_config_dir() / "settings.json"


def load_settings() -> Dict[str, Any]:
    """Load settings from file."""
    path = get_settings_path()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return DEFAULT_SETTINGS | json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return DEFAULT_SETTINGS.copy()


def save_settings(settings: Dict[str, Any]) -> None:
    """Save settings to file."""
    path = get_settings_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)


def get_setting(key: str, default: Any = None) -> Any:
    """Get a single setting value."""
    settings = load_settings()
    return settings.get(key, default)


def set_setting(key: str, value: Any) -> None:
    """Set a single setting value."""
    settings = load_settings()
    settings[key] = value
    save_settings(settings)