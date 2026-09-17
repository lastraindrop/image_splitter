"""Simple keybinding system for CLI and GUI."""
import copy
import json
from pathlib import Path
from typing import Dict, Optional

from image_splitter.settings import get_config_dir

DEFAULT_KEYMAP = {
    "global": {
        "<Control-o>": "select_files",
        "<Control-Return>": "run_batch",
        "<Delete>": "remove_selected",
        "<Control-Shift-Delete>": "clear_list",
        "<Control-grave>": "toggle_console",
        "<Control-p>": "toggle_pipeline",
        "<Control-Shift-R>": "toggle_macro_record",
        "<Control-z>": "undo_history",
        "<Control-Shift-Z>": "redo_history",
        "<Control-e>": "open_output_dir",
        "<Escape>": "stop_tasks",
    }
}


def get_keymap_path() -> Path:
    """Get keymap file path."""
    return get_config_dir() / "keymap.json"


def load_keymap() -> Dict[str, Dict[str, str]]:
    """Load keymap from file.

    Returns a deep copy of the defaults when no user keymap exists, so
    that callers mutating the result (e.g. :func:`bind`) cannot leak
    changes into the module-level ``DEFAULT_KEYMAP``.

    V15: a keymap.json containing valid-but-non-dict JSON previously
    leaked through and crashed ``km.get("global")`` with AttributeError.
    Non-dict payloads now fall back to defaults.
    """
    path = get_keymap_path()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
            import logging
            logging.getLogger(__name__).warning(
                "keymap.json is not a JSON object — using defaults"
            )
        except (json.JSONDecodeError, IOError):
            pass
    return copy.deepcopy(DEFAULT_KEYMAP)


def save_keymap(keymap: Dict[str, Dict[str, str]]) -> None:
    """Save keymap to file."""
    path = get_keymap_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(keymap, f, indent=2, ensure_ascii=False)
    except (IOError, OSError) as e:
        import logging
        logging.getLogger(__name__).warning("Failed to save keymap: %s", e)


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
    save_keymap(copy.deepcopy(DEFAULT_KEYMAP))


def get_context_actions(context: str) -> Dict[str, str]:
    """Get all actions for a context."""
    keymap = load_keymap()
    return keymap.get(context, {})