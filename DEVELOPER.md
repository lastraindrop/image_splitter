# Developer Guide

Comprehensive guidance for extending and contributing to Image Splitter Pro.

## Architecture Overview

The project follows an **Operator-Based** design philosophy, aligned with professional tools like Blender. Every processing function is an independent operator that can be invoked via CLI, GUI, or script.

```
image_splitter/
├── engine/                  # Core engine (generic dispatch)
│   ├── base.py              # Abstract base classes
│   ├── registry.py          # Plugin registration (singleton + dedup)
│   ├── dispatcher.py        # Command parsing and chaining
│   ├── config_coercion.py   # Parameter type coercion
│   ├── history.py           # Operation history (undo/redo)
│   ├── macro.py             # Macro recording & playback
│   └── presets.py           # Parameter presets system
├── processors/              # Processor plugins (10 built-in)
├── plugins/                 # User plugin directory (auto-discovered)
│   └── example_plugin.py    # Example: invert colors
├── core.py                  # Processing pipeline + auto-discovery
├── cli.py                   # CLI entry point (multiprocessing)
├── gui.py                   # GUI entry point (history/macro/console/presets/pipeline)
├── settings.py              # User settings persistence
├── keymap.py                # Keybinding system
├── script_engine.py         # Batch scripting engine
├── logging_config.py        # Logging configuration
├── models.py                # Configuration models (10 validated dataclasses)
├── ui/                      # UI components
│   ├── console.py           # Interactive command console
│   └── pipeline.py          # Visual pipeline chain editor
├── tests/                   # Test suite (218 tests, 25 files)
├── .github/workflows/
│   └── ci.yml               # CI/CD pipeline
└── pyproject.toml           # Package configuration
```

## Core Design Principles

### 1. Everything as Operators

Every processing function (splitting, resizing, etc.) is abstracted as a `Processor` plugin. The core engine discovers plugins through `Registry` and supports string-based command invocation through `CommandDispatcher`.

**Example:**
```python
# CLI
python cli.py image.png --processor grid_splitter --set rows=3

# Chain
python cli.py image.png --chain "resizer(width=0.5)|grid_splitter(rows=2)"

# Preset
python cli.py image.png --preset "web_export"

# Script
# file: script.txt
resizer width=0.5
filters grayscale=True
format_converter format=WebP quality=80
```

### 2. Metadata-Driven UI

Processors self-describe their required parameters via `get_ui_metadata()`. The GUI automatically renders input controls based on this metadata, eliminating hardcoded UI logic.

```python
def get_ui_metadata(self) -> List[Dict[str, Any]]:
    return [
        {"name": "rows", "label": "Rows", "type": "int", "default": 3},
        {"name": "cols", "label": "Cols", "type": "int", "default": 3},
    ]
```

### 3. Resource Safety

- All image operations use `with Image.open(...)` context management
- Cropped copies are closed immediately after processing in `finally` blocks
- ICC profiles are preserved through all crop/split operations
- Intermediate chain images are properly closed via dispatcher

### 4. Fail-Fast Validation

All external input must be validated for type, range, and physical validity before I/O operations. The model layer (`models.py`) handles parameter structuration with `__post_init__` validation:

- `SplitConfig`: rows/cols positive, offsets non-negative
- `GeometryConfig`: angle in {0, 90, 180, 270}
- `FormatConfig`: format in {WebP, JPEG, PNG, BMP}, quality 1-100
- `WatermarkConfig`: size positive, opacity 0-255, anchor in {TL, TR, BL, BR, C}

### 5. Code Style

- Follows [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- Full mypy static type checking — **zero type errors enforced**
- Imports grouped: standard library → third-party → local, alphabetically
- Type annotations on all public functions and methods
- Path handling uses `pathlib.Path` for cross-platform robustness
- Logging uses standard `logging` module instead of `print()`

## Creating a New Processor

### Step 1: Create the Processor File

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
        return "Edit"  # Split | Transform | Edit | Filter | Export

    @property
    def tool_tip(self) -> str:
        return "Description for tooltip."

    @property
    def config_model(self) -> type | None:
        from image_splitter.models import MyCustomConfig
        return MyCustomConfig

    def get_ui_metadata(self) -> List[Dict[str, Any]]:
        return [
            {"name": "param1", "label": "Parameter 1", "type": "int", "default": 10},
            {"name": "param2", "label": "Parameter 2", "type": "str", "default": "value"},
        ]

    def process(
        self, image: Image.Image, config: Dict[str, Any]
    ) -> List[Tuple[Image.Image, Dict[str, Any]]]:
        result_image = image.copy()
        context = {"action": "custom_processed", "param1": config.get("param1")}
        return [(result_image, context)]

    def draw_preview(
        self, canvas: Any, thumb_size: Tuple[int, int],
        canvas_pos: Tuple[int, int], ratio: float,
        props: Dict[str, Any], theme: Any
    ) -> None:
        pass
```

### Step 2: Define Configuration Model (Recommended)

In `models.py`:
```python
@dataclass
class MyCustomConfig:
    param1: int = 10
    param2: str = "value"

    def __post_init__(self) -> None:
        if self.param1 <= 0:
            raise ValueError("param1 must be positive")
```

### Step 3: Auto-Discovery

`register_all_processors()` scans both `processors/` and `plugins/` directories. No manual registration needed. User plugins are first-class citizens equal to built-in processors.

## Parameter Consistency Protocol

To ensure UI stability and prevent naming conflicts:

1. **Model-Driven Validation**: All processor parameters must be pre-validated through models in `models.py`.
2. **Coercion Mechanism**: Raw input (CLI strings or GUI variables) must be converted via `coerce_processor_config()` to ensure type alignment with `config_model`.
3. **Context Injection**: Processors must inject core parameters into the returned `context` dictionary to support template substitution.
4. **System Variables**: `core.py` provides `{w}`, `{h}`, `{index}`, `{filename}`, `{ext}` by default. Processors inject `{row}`, `{col}`, `{anchor}`, `{text}`, `{quality}`, etc.

## Testing

```bash
# Full suite
python -m pytest tests/ -v

# Non-GUI only (for headless CI)
python -m pytest tests/ -v -k "not gui and not ui_preview"

# Specific file
python -m pytest tests/test_operator_compliance.py -v

# With coverage
python -m pytest tests/ --cov=image_splitter

# Type check
python -m mypy image_splitter --ignore-missing-imports
```

### Test Architecture

| Layer | Test Files | Purpose |
|-------|-----------|---------|
| **Engine** | test_engine_v4, test_config_coercion, test_dispatcher, test_history, test_operator_compliance | Core framework validation |
| **Processors** | test_adjuster, test_custom_splitter, test_edge_cases, test_error_paths, test_processors_expanded, test_save_compatibility | Per-processor correctness |
| **Entry Points** | test_cli, test_gui_smoke, test_gui_workflows, test_ui_preview | Integration with entry points |
| **Infrastructure** | test_settings, test_keymap, test_script_engine, test_macro, test_presets, test_plugin | Supporting systems |
| **Regression** | test_bug_fixes | Bug prevention |
| **Integration** | test_integration, test_workflow | End-to-end workflows |

All tests use shared fixtures from `tests/conftest.py` — the `BaseTest` class provides auto-adapting test images, temp directories, and processor registration.

## Logging

```python
import logging
logger = logging.getLogger(__name__)

def process(self, image, config):
    logger.debug("Processing with param1=%d", config.get("param1"))
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

### Completed (V8.0)
- [x] 10 core processors + 1 plugin example
- [x] Google Python Style + full mypy compliance (0 errors)
- [x] 22+ bug fixes (BUG-01 through BUG-40)
- [x] Operation history (undo/redo) + JSON export
- [x] Macro recording & playback
- [x] Interactive command console
- [x] Parameter presets system (save/load/import/export)
- [x] Visual pipeline chain editor (Ctrl+P)
- [x] Cross-platform font handling
- [x] CI/CD pipeline (GitHub Actions, 12 OS×Python combos)
- [x] 218 tests, 25 test files, 95%+ coverage
- [x] Static type checking — mypy 0 errors

### Short-Term
- [ ] Parallel batch pipeline execution from GUI
- [ ] Proxy/JPEG preview for large file handling

### Long-Term
- [ ] Distributed processing (RPC-based multi-node)
- [ ] WASM edition (browser-based offline processing)

---

See [TECHNICAL.md](./TECHNICAL.md) for the complete technical guide with principles, processes, and parameter alignment details.
