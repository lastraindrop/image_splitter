# Developer Guide

This document provides comprehensive guidance for developers who want to extend or contribute to Image Splitter Pro.

## Architecture Overview

The project follows a **Operator-Based** design philosophy, aligned with professional tools like Blender. Every processing function is an independent operator that can be invoked via CLI, GUI, or script.

```
image_splitter/
├── engine/                 # Core engine (generic dispatch)
│   ├── base.py           # Abstract base classes
│   ├── registry.py       # Plugin registration center
│   ├── dispatcher.py   # Command parsing and chaining
│   ├── config_coercion.py  # Parameter type coercion
│   ├── history.py        # Operation history (undo/redo)
│   └── macro.py          # Macro recording & playback
├── processors/           # Processor plugins (10 built-in)
├── plugins/              # User plugin directory
│   └── example_plugin.py # Example: invert colors
├── core.py              # Processing pipeline + auto-discovery
├── cli.py               # CLI entry point
├── gui.py               # GUI entry point (history/macro/console)
├── settings.py          # User settings persistence
├── keymap.py           # Keybinding system
├── script_engine.py    # Batch scripting engine
├── logging_config.py    # Logging configuration
├── models.py             # Configuration models
├── ui/                  # UI components
│   └── console.py       # Interactive command console
├── tests/               # Test suite (176 tests)
└── pyproject.toml      # Package configuration
```

## Core Design Principles

### 1. Everything as Operators

Every processing function (splitting, resizing, etc.) is abstracted as a `Processor` plugin. The core engine discovers plugins through `Registry` and supports string-based command invocation through `CommandDispatcher`.

**Example:**
```python
# CLI
python cli.py image.png --processor grid_splitter --set rows=3

# Or chain
python cli.py image.png --chain "resizer(width=0.5)|grid_splitter(rows=2)"
```

### 2. Metadata-Driven UI

Processors self-describe their required parameters via `get_ui_metadata()`. The GUI automatically renders input controls based on this metadata, eliminating hardcoded UI logic.

**Example processor metadata:**
```python
def get_ui_metadata(self) -> List[Dict[str, Any]]:
    return [
        {"name": "rows", "label": "Rows", "type": "int", "default": 3},
        {"name": "cols", "label": "Cols", "type": "int", "default": 3},
    ]
```

### 3. Resource Safety

- All image operations use `with Image.open(...)` context management
- Cropped copies are closed immediately after processing
- Memory峰值 is strictly controlled

### 4. Fail-Fast Validation

All external input must be validated for type, range, and physical validity before I/O operations. The model layer (`models.py`) handles parameter structuration, while core logic handles business validation.

### 5. Code Style

- Follows [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- All core functions include complete Google-style Docstrings
- Imports grouped: standard library → third-party → local, alphabetically within each group
- Type annotations required on all public functions and methods
- Path handling uses `pathlib.Path` for cross-platform robustness
- Logging uses the standard `logging` module instead of `print()`

## Creating a New Processor

### Step 1: Create the Processor File

Create a new Python file in the `processors/` directory:

```python
"""My custom processor module."""

from typing import Any, Dict, List, Tuple
from PIL import Image
from image_splitter.engine.base import BaseProcessor


class MyCustomProcessor(BaseProcessor):
    """Description of what this processor does."""

    @property
    def name(self) -> str:
        return "my_custom_processor"

    @property
    def display_name(self) -> str:
        return "My Custom Processor"

    @property
    def category(self) -> str:
        return "Edit"  # Options: Split, Transform, Edit, Filter, Export

    @property
    def tool_tip(self) -> str:
        return "Description for tooltip."

    @property
    def config_model(self) -> type:
        # Link to a config dataclass in models.py
        from image_splitter.models import MyCustomConfig
        return MyCustomConfig

    def get_ui_metadata(self) -> List[Dict[str, Any]]:
        return [
            {"name": "param1", "label": "Parameter 1", "type": "int", "default": 10},
            {"name": "param2", "label": "Parameter 2", "type": "str", "default": "value"},
        ]

    def process(
        self,
        image: Image.Image,
        config: Dict[str, Any]
    ) -> List[Tuple[Image.Image, Dict[str, Any]]]:
        """Core processing logic."""
        # Your logic here
        result_image = image.copy()
        
        context = {
            "param1": config.get("param1"),
            "custom_key": "custom_value",  # For template substitution
        }
        
        return [(result_image, context)]

    def draw_preview(
        self,
        canvas,
        thumb_size,
        canvas_pos,
        ratio,
        props,
        theme
    ) -> None:
        """Draw preview overlay on GUI canvas."""
        pass
```

### Step 2: Define Configuration Model (Optional but Recommended)

In `models.py`:

```python
@dataclass
class MyCustomConfig:
    param1: int = 10
    param2: str = "value"

    def __post_init__(self):
        if self.param1 <= 0:
            raise ValueError("param1 must be positive")
```

### Step 3: The Processor is Auto-Discovered

Run `register_all_processors()` - it automatically scans and loads all processors
in both the `processors/` package and the `plugins/` directory. No manual
registration needed. User plugins are first-class citizens equal to built-in processors.

## Parameter Consistency Protocol

To ensure UI stability and prevent naming conflicts:

1. **Model-Driven Validation**: All processor parameters must be pre-validated through models in `models.py`.

2. **Coercion Mechanism**: Raw input (CLI strings or GUI variables) must be converted via `coerce_processor_config()` to ensure type alignment with `config_model`.

3. **Context Injection**: Processors must inject core parameters into the returned `context` dictionary to support template substitution.

4. **System Variables**: `core.py` provides `{w}`, `{h}`, `{index}`, `{filename}` by default.

## Testing

All new processors must pass the compliance tests:

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_operator_compliance.py -v

# Run with coverage
python -m pytest tests/ --cov=image_splitter
```

### Required Test Coverage

- Processor smoke test (default configuration works)
- Metadata completeness (name, label, type, default)
- Parameter coercion (type conversion)
- UI addressability (can be rendered in GUI)
- Edge case resilience (invalid inputs, boundary values, special image modes)
- Integration tests (end-to-end pipeline, script engine, CLI chain mode)
- Keymap persistence (bind/unbind, save/load, reset)
- Settings persistence (round-trip, merge with defaults, corrupt JSON resilience)
- History system (push, undo, redo, max-depth eviction, JSON export)
- Macro system (record, stop, generate script, playback, save)
- Plugin auto-discovery (external directory scanning, equality with built-in)
- Console interaction (command input, tab completion, history navigation)

## New Systems (v7.0)

### Operation History

```python
from image_splitter.engine.history import HistoryManager, HistoryEntry
import time

history = HistoryManager(max_depth=50)
history.push(HistoryEntry(
    timestamp=time.time(),
    operator_name="grid_splitter",
    config_snapshot={"rows": 3, "cols": 3},
    input_files=["image.png"],
    description="Grid split 3x3",
))
# Undo surfaces parameters for inspection
entry = history.undo()
# Redo replays the operation
history.redo()
# Export to JSON
history.export_log("history.json")
```

### Macro Recording

```python
from image_splitter.engine.macro import MacroRecorder, MacroPlayer

recorder = MacroRecorder()
recorder.start()
recorder.record("grid_splitter", {"rows": 3, "cols": 2})
recorder.record("resizer", {"width": 0.5, "height": 0.5})
script = recorder.stop()  # Returns executable Python script
recorder.save("my_macro.py")

# Replay
result = MacroPlayer.play("my_macro.py", ["input.png"], "./output")
```

### Console (GUI)

The console panel supports:
- Direct operator invocation: `grid_splitter rows=3 cols=2`
- Chain commands: `resizer width=0.5 | grid_splitter rows=2 cols=2`
- Command history (Up/Down arrows)
- Tab completion for operator names

### Plugin System

Create a file in `plugins/` with a `BaseProcessor` subclass — it's auto-discovered on startup. See `plugins/example_plugin.py` for a complete example.

## Logging

Use the logging module for all output:

```python
import logging

logger = logging.getLogger(__name__)

def process(self, image, config):
    logger.debug("Processing with param1=%d", config.get("param1"))
    # ...
    logger.info("Processed %d tiles", len(results))
```

## Path Handling

Always use `pathlib.Path` for cross-platform compatibility:

```python
from pathlib import Path

def save_output(image: Image.Image, output_dir: str, filename: str) -> Path:
    output_path = Path(output_dir) / filename
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    return output_path
```

## Roadmap

### Completed
- [x] **V4.0 Architecture**: Fully decoupled plugin auto-discovery
- [x] **Feature Library**: 10 core processors + 1 plugin example
- [x] **Compliance Testing**: Automated plugin protocol detection
- [x] **UI Enhancement**: Adaptive controls with type validation
- [x] **V5.5 Refactor**: Google Python Style compliance
- [x] **V6.0 Hardening**: Full Google Python Style audit, 22 bug fixes
- [x] **V7.0 Blender Systems**: Operation history (undo/redo), macro recording/playback, interactive console, plugin system
- [x] **Test Suite**: 176 tests across 23 files, 100% pass rate

### Short-Term Goals
- [ ] **Static Type Checking**: Integrate mypy for full type scanning
- [ ] **Visual Pipeline Editor**: Drag-and-drop processor cards in GUI
- [ ] **CI/CD Pipeline**: Automated testing with GitHub Actions

### Long-Term Goals
- [ ] **Distributed Processing**: RPC-based multi-node rendering
- [ ] **WASM Edition**: Browser-based offline processing