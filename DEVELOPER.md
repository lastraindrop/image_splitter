# Developer Guide

Comprehensive guidance for extending and contributing to Image Splitter Pro.

## Architecture Overview

The project follows an **Operator-Based** design philosophy with a **unified Node Graph execution engine**, aligned with professional tools like Blender. Every processing function is an independent operator; the engine provides typed properties, data blocks, a node graph evaluator, and a framework-agnostic GuiState ViewModel.

```
image_splitter/
├── engine/                  # Core engine
�?  ├── base.py              # BaseProcessor/BaseConfig ABCs
�?  ├── registry.py          # Plugin registration (singleton + dedup)
�?  ├── dispatcher.py        # Command parsing and chaining
�?  ├── config_coercion.py   # Parameter type coercion
�?  ├── history.py           # Operation history (undo/redo)
�?  ├── macro.py             # Macro recording & sandboxed playback
�?  ├── presets.py           # Parameter presets system
�?  ├── props.py             # Typed Property descriptors (Experimental)
�?  ├── data_blocks.py       # ImageDataBlock (named, versioned, ref-counted)
�?  ├── nodes.py             # DAG node graph (Socket, BaseNode, 4 concrete nodes)
�?  ├── evaluator.py         # NodeGraph evaluator + LRU EvaluationCache
�?  ├── legacy_adapter.py    # ProcessorNodeAdapter + ChainAsGraph (unified execution bridge)
�?  └── _ui_metadata_util.py # Auto-generate UI metadata from dataclass fields
├── processors/              # Processor plugins (13 built-in)
├── plugins/                 # User plugin directory (auto-discovered)
├── core.py                  # Processing pipeline + unified Node Graph execution
├── cli.py                   # CLI entry point (multiprocessing)
├── gui.py                   # GUI (customtkinter + GuiState ViewModel)
├── settings.py              # User settings persistence
├── keymap.py                # Keybinding system (8 global shortcuts)
├── script_engine.py         # Batch scripting engine
├── logging_config.py        # Logging configuration
├── models.py                # Configuration models (13 validated dataclasses)
├── ui/                      # UI components
�?  ├── _state.py            # GuiState �?framework-agnostic ViewModel
�?  ├── console.py           # Interactive command console (customtkinter)
�?  ├── pipeline.py          # Visual pipeline chain editor (customtkinter)
�?  └── param_widgets.py     # Shared parameter widget factory (customtkinter)
├── tests/                   # Test suite (498 tests, 41 files)
└── pyproject.toml           # Package configuration
```

## Engine Layer (New �?V9.0)

### Property System (`engine/props.py`)

Typed descriptors with coercion, validation, and update callbacks:

```python
from image_splitter.engine.props import IntProp, FloatProp, BoolProp, EnumProp, ListProp

class MyConfig:
    width = IntProp(default=100, min_val=1, max_val=4096)
    ratio = FloatProp(default=1.0, min_val=0.1, max_val=10.0)
    enabled = BoolProp(default=True)
    mode = EnumProp(options=["fast", "quality"], default="quality")
    guides = ListProp(default=[100, 200, 300])
```

### ImageDataBlock (`engine/data_blocks.py`)

Named, versioned, reference-counted image containers:

```python
from image_splitter.engine.data_blocks import ImageDataBlock

block = ImageDataBlock(name="my_image", image=pil_image)
block.use()       # increment ref count
block.version     # auto-incremented on image change
block.touch()     # force version bump for cache invalidation
clone = block.clone("copy")  # independent copy
ImageDataBlock.clear_all()    # release all blocks
```

### Node Graph (`engine/nodes.py` + `engine/evaluator.py`)

DAG-based processing pipeline with dirty propagation:

```python
from image_splitter.engine.nodes import ImageInputNode, ColorAdjustNode, ImageOutputNode
from image_splitter.engine.evaluator import NodeGraph

graph = NodeGraph()
inp = ImageInputNode("in"); inp.set_prop("source", "my_block")
adj = ColorAdjustNode("adj"); adj.set_prop("brightness", 1.2)
out = ImageOutputNode("out"); out.set_prop("target", "result")

graph.add_node(inp); graph.add_node(adj); graph.add_node(out)
graph.connect("in", "image", "adj", "image")
graph.connect("adj", "image", "out", "image")
graph.evaluate(force_all=True)
```

### Legacy Adapter (`engine/legacy_adapter.py`)

Zero-break migration �?wraps existing processors as nodes:

```python
from image_splitter.engine.legacy_adapter import ChainAsGraph

# Drop-in replacement for CommandDispatcher.execute_chain()
results = ChainAsGraph.execute_chain(image, "resizer(width=0.5)|custom_splitter(h_lines=[100,200],v_lines=[133,266])")
# Returns List[Image.Image] �?identical to CommandDispatcher output
```

## Core Design Principles

### 1. Everything as Operators

Every processing function (splitting, resizing, etc.) is abstracted as a `Processor` plugin. The core engine discovers plugins through `Registry` and supports multiple invocation paths:

```python
# Direct CLI
python -m image_splitter.cli image.png -p grid_splitter --set rows=3 --set cols=2

# Chain (Python function-call syntax)
python -m image_splitter.cli image.png --chain "resizer(width=0.5)|grid_splitter(rows=2,cols=2)"

# Custom splitter with arbitrary guides
python -m image_splitter.cli image.png --chain "custom_splitter(h_lines=[100,300,500],v_lines=[200,400])"

# Preset
python -m image_splitter.cli image.png --preset "web_export"

# Script file
# script.txt:
resizer width=0.5
filters grayscale=True
format_converter format=WebP quality=80
```

### 2. Metadata-Driven UI

Processor parameters are defined once in their dataclass model via `field(metadata={"label": ...})`. The UI metadata is auto-generated by `_ui_metadata_util.ui_metadata_from_dataclass()`:

```python
from dataclasses import dataclass, field

@dataclass
class MyConfig:
    quality: int = field(default=80, metadata={"label": "Quality (1-100)"})
    mode: str = field(default="fast", metadata={
        "label": "Mode", "options": ["fast", "quality", "balanced"]
    })
```

The `BaseProcessor.get_ui_metadata()` method calls this utility automatically �?no hand-written metadata lists needed. Supported types: `int`, `float`, `bool`, `enum` (via options), `str`, `list`.

### 3. Resource Safety

- All image operations use `with Image.open(...)` context management
- ICC profiles are preserved through all crop/split operations **and** the
  chain paths (`ScriptEngine.chain`, GUI `_run_chain_thread`) since V14
- Temporary `ImageDataBlock`s use **unique per-call names**
  (`__proc_input_{uid}__`) �?never reuse the `__proc_*` / `__chain_*` prefix
  for fixed names; the class-level registry is shared global state
- `_execute_via_graph` and `ChainAsGraph` clean temp blocks in `try/finally` �?  keep it that way when touching the graph builders
- `ImageDataBlock.clear_all()` releases all blocks; multi-output results are
  safely copied before cleanup

### 4. Thread Safety

- All 3 worker threads (`work_thread`, `_run_chain_thread`, `_console_execute`) receive a snapshot of `self.current_files` before spawning
- `threading.Event` for graceful abort; no shared mutable state between threads
- GUI operations are serialized by the `_busy` flag (batch / console /
  pipeline mutually exclusive)

### 5. Fail-Fast Validation

All external input must be validated for type, range, and physical validity before I/O operations. The model layer (`models.py`) handles parameter structuration with `__post_init__` validation:

- `SplitConfig`: rows/cols positive, offsets non-negative
- `CustomSplitConfig`: h_lines + v_lines must be lists of non-negative ints
- `GeometryConfig`: angle in {0, 90, 180, 270}
- `FormatConfig`: format in {WebP, JPEG, PNG, BMP}, quality 1-100
- `WatermarkConfig`: size positive, opacity 0-255, anchor in {TL, TR, BL, BR, C}

### 6. Code Style

- Follows [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- Full mypy static type checking �?**zero type errors enforced across 44 source files**
- Imports grouped: standard library �?third-party �?local, alphabetically
- Type annotations on all public functions and methods
- Path handling uses `pathlib.Path` for cross-platform robustness
- Logging uses standard `logging` module instead of `print()`
- UI colors centralized in `UITheme` class; panels use injected theme via `_c()` helper

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
            {"name": "param2", "label": "Parameter 2", "type": "enum", "default": "a", "options": ["a", "b", "c"]},
            {"name": "guides", "label": "Guide Lines", "type": "list", "default": [100, 200]},
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
    param2: str = "a"
    guides: List[int] = field(default_factory=lambda: [100, 200])

    def __post_init__(self) -> None:
        if self.param1 <= 0:
            raise ValueError("param1 must be positive")
```

### Step 3: Auto-Discovery

`register_all_processors()` scans both `processors/` and `plugins/` directories. No manual registration needed. User plugins are first-class citizens equal to built-in processors (registering a duplicate `name` replaces the built-in with a warning).

## GUI Contributor Notes (V14)

- **New global keybinding?** Bind through `_bind_keymap()` only �?the
  typing-context guard (`_is_typing_context`) suppresses global actions while
  the user is typing in an entry/combo/text widget. Do not add raw
  `self.root.bind(...)` calls elsewhere.
- **New GUI tests that need keyboard focus?** Use `TkTestCase(map_offscreen=True)`
  from conftest + `focus_set()` on a mapped window. Withdrawn windows cannot
  take focus and `focus_force()` is unreliable under test runners on Windows.
- **Persisting user paths/names to disk?** Sanitize with the
  `presets._ILLEGAL_NAME_CHARS` regex pattern (see `_preset_path`) �?preset
  names with e.g. `:` previously crashed on Windows.
- **GUI diagnostics** go through `logging` �?they land in
  `~/.image_splitter/logs/gui.log` (rotating) via `setup_file_logging()`.

## Parameter Consistency Protocol

To ensure UI stability and prevent naming conflicts:

1. **Model-Driven Validation**: All processor parameters must be pre-validated through models in `models.py`.
2. **Coercion Mechanism**: Raw input (CLI strings or GUI variables) must be converted via `coerce_processor_config()` to ensure type alignment with `config_model`.
3. **List Parameters**: List-type parameters (e.g., `h_lines`, `v_lines` for custom splitter) use `ast.literal_eval` for CLI parsing and are stored as Python lists �?no hardcoded length limits.
4. **Context Injection**: Processors must inject core parameters into the returned `context` dictionary to support template substitution.
5. **System Variables**: `core.py` provides `{w}`, `{h}`, `{index}`, `{filename}`, `{ext}` by default. Processors inject `{row}`, `{col}`, `{anchor}`, `{text}`, `{quality}`, etc.
6. **Dynamic Alignment**: When adding new processor parameters, verify alignment across all 3 layers: model (`models.py`) �?UI metadata (`get_ui_metadata()`) �?runtime (`process()` config dict).

## Testing

```bash
# Full suite
python -m pytest tests/ -v

# Full suite (GUI tests skip if the [gui] extra is absent)
python -m pytest tests/ -q

# Engine layer tests
python -m pytest tests/test_props.py tests/test_data_blocks.py tests/test_node_graph.py tests/test_legacy_adapter.py -v

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
| **Engine (new)** | test_props, test_data_blocks, test_node_graph, test_legacy_adapter | Property system, data blocks, node graph, adapter integration |
| **Engine (legacy)** | test_engine_v4, test_config_coercion, test_dispatcher, test_history, test_operator_compliance | Core framework validation |
| **Processors** | test_adjuster, test_custom_splitter, test_edge_cases, test_error_paths, test_processors_expanded, test_save_compatibility | Per-processor correctness |
| **Entry Points** | test_cli, test_gui_smoke, test_gui_workflows, test_ui_preview | Integration with entry points |
| **Infrastructure** | test_settings, test_keymap, test_script_engine, test_macro, test_presets, test_plugin | Supporting systems |
| **Regression** | test_bug_fixes | Bug prevention |
| **Integration** | test_integration, test_workflow | End-to-end workflows |

All tests use shared fixtures from `tests/conftest.py` �?the `BaseTest` class provides auto-adapting test images, temp directories, and processor registration.

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

> Living roadmap maintained in [PLAN.md](./PLAN.md); audit history in
> REPORT_V15.md. Summary as of V16.0 (0.8.0):

### Completed (V13–V16)
- [x] Packaging repair (standard layout) �?V13
- [x] Unified execution with zero second path �?CommandDispatcher delegates
- [x] Interaction-path audit: dashed border, macro chain playback, keymap
      typing guard, graph exception leak, CLI settings defaults, chain ICC,
      preset sanitization, UUID temp blocks, GUI file log �?V14
- [x] Chain fan-out for mid-chain splitters; 1 defensive copy per invocation;
      GUI startup parameter panel; config robustness; smart_crop light
      backgrounds �?V15
- [x] Shared parallel runner (CLI+GUI) with cancel-pending abort; `{batch}`
      placeholder; registry duplicate policy; LICENSE + 0.8.0; sdist/wheel +
      clean-venv smoke; PyInstaller onefile; CI GUI-import hardening �?V16
- [x] 498 tests / 41 files, mypy 0 errors, ruff clean

### Short-Term
- [ ] Unify the two metadata tracks (dataclass metadata vs get_ui_metadata overrides)
- [ ] Real-machine GUI smoke pass before release
- [ ] PyPI publish (`python -m build && twine upload dist/*`)

### Long-Term
- [ ] Visual node graph editor (drag-connect)
- [ ] Plugin hot-reload
- [ ] Per-op contexts (row/col) threaded through chain naming
- [ ] Distributed processing / WASM edition / plugin marketplace

---

See [TECHNICAL.md](./TECHNICAL.md) for the complete technical guide with principles, processes, and parameter alignment details.
