"""Simple keybinding system for CLI and GUI."""
import json
from pathlib import Path
from typing import Dict, Optional

from image_splitter.settings import get_config_dir

DEFAULT_KEYMAP = {
    "global": {
        "<Control-o>": "select_files",
        "<Control-Return>": "run_batch",
        "<Delete>": "remove_selected",
    }
}


def get_keymap_path() -> Path:
    """Get keymap file path."""
    return get_config_dir() / "keymap.json"


def load_keymap() -> Dict[str, Dict[str, str]]:
    """Load keymap from file."""
    path = get_keymap_path()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return DEFAULT_KEYMAP.copy()


def save_keymap(keymap: Dict[str, Dict[str, str]]) -> None:
    """Save keymap to file."""
    path = get_keymap_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(keymap, f, indent=2, ensure_ascii=False)


def bind(context: str, key_sequence: str, action: str) -> None:
    """Bind a key sequence to an action in a context."""
    keymap = load_keymap()
    if context not in keymap:
        keymap[context] = {}
    keymap[context][key_sequence] = action
    save_keymap(keymap)


def unbind(context: str, key_sequence: str) -> None:
    """Unbind a key sequence from an action."""
    keymap = load_keymap()
    if context in keymap and key_sequence in keymap[context]:
        del keymap[context][key_sequence]
        save_keymap(keymap)


def lookup(context: str, key_sequence: str) -> Optional[str]:
    """Look up action for a key sequence in a context."""
    keymap = load_keymap()
    return keymap.get(context, {}).get(key_sequence)


def reset_to_default() -> None:
    """Reset keymap to default."""
    save_keymap(DEFAULT_KEYMAP.copy())


def get_context_actions(context: str) -> Dict[str, str]:
    """Get all actions for a context."""
    keymap = load_keymap()
    return keymap.get(context, {})