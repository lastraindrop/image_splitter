# Technical Guide — Image Splitter Pro

> Comprehensive technical reference covering architecture principles,
> processing pipeline details, parameter alignment protocol, and test methodology.

---

## 1. Processing Pipeline (Detailed)

### 1.1 Entry Flow

```
User Input (CLI/GUI/Script)
    │
    ├── CLI: argparse → process_image()
    ├── GUI: tkinter → threading.Thread → batch_process_images()
    └── Script: ScriptEngine → process_image()
    │
    ▼
process_image(image_path, processor_name, config)
    │
    ├── 1. register_all_processors() (if empty)
    ├── 2. Path.exists() check → fail-fast
    ├── 3. ProcessorRegistry.get(name) → ValueError if not found
    ├── 4. coerce_processor_config(processor, raw_dict)
    │       └── int/float/bool/list/enum/str coercion via metadata
    ├── 5. config_model(**model_input) → __post_init__ validation
    ├── 6. Image.open() → processor.process(image, config_dict)
    │       └── Returns List[(Image, context_dict)]
    ├── 7. For each (cell, context):
    │       ├── template.format(**merged_context)
    │       ├── safe_name extraction (path traversal guard)
    │       ├── _prepare_image_for_save() (JPEG/BMP transparency)
    │       ├── ICC profile preservation
    │       └── cell.save(save_path, **save_args)
    └── 8. finally: close cell images
```

### 1.2 Chain Execution Flow

```
CommandDispatcher.execute_chain(image, cmd_str, extra_config=None)
    │
    ├── parse_command(cmd_str) → List[(op_name, props)]
    │       └── ast.literal_eval for type-safe parameter parsing
    │
    ├── For each (op_name, props):
    │       ├── ProcessorRegistry.get(op_name)
    │       ├── props = {**extra_config, **props}
    │       ├── coerce_processor_config(processor, props)
    │       ├── For each img in current_images:
    │       │       ├── processor.process(img, coerced_props)
    │       │       └── close(img) if img != original
    │       └── current_images = next_step_images
    │
    └── return current_images (python List of PIL Images)
```

### 1.3 Concurrency Model

| Mode | Mechanism | Isolation |
|------|-----------|-----------|
| CLI (single) | Serial in-process | N/A |
| CLI (parallel) | `ProcessPoolExecutor` (true multiprocessing) | Process-level |
| GUI (batch) | `threading.Thread` + `Event` | Thread-level |
| GUI (console) | `threading.Thread` (daemon) | Thread-level |
| Script (chain) | Serial in-process | N/A |

---

## 2. Node Graph Engine

### 2.1 Property System

The typed Property descriptor system (`engine/props.py`) provides Blender `bpy.props`-style descriptors with coercion, validation, and update callbacks:

| Property | Type | Factory | Coercion |
|----------|------|---------|----------|
| `_IntProperty` | `int` | `IntProp(default=0, min_val=0)` | float→int truncate, str→int |
| `_FloatProperty` | `float` | `FloatProp(default=0.0, min=0.0, max=1.0)` | int→float, str→float |
| `_BoolProperty` | `bool` | `BoolProp(default=False)` | `"true"/"yes"/"1"`→True, `"false"/"no"/"0"`→False |
| `_EnumProperty` | `str` | `EnumProp(options=[...], default=...)` | `str(value).strip()` |
| `_StrProperty` | `str` | `StrProp(default="")` | `str(value)` |
| `_ListProperty` | `list` | `ListProp(default=[])` | `ast.literal_eval(value)` |
| `_ColorProperty` | `tuple` | `ColorProp(default=(255,255,255,255))` | `ast.literal_eval(value)` |

All properties implement `to_ui_metadata()` returning a dict with `name`, `label`, `type`, `default`, and optional `min`, `max`, `options`, `ui_type` keys — compatible with the existing `get_ui_metadata()` format.

### 2.2 ImageDataBlock

`ImageDataBlock` (Blender ID-block pattern) — named, versioned, reference-counted image containers:

```
Class-level registry: _name_registry: dict[str, ImageDataBlock]

Lifecycle:
  1. __init__(name, image)     → registers in _name_registry
  2. image setter              → version += 1, extract metadata
  3. use() / unuse()           → ref-count ±1; at 0 → release()
  4. release()                 → image.close(); _image = None
  5. clone(new_name)           → independent copy, version=0
  6. clear_all()               → release all, clear registry

Cache key: (node_name, node_version) — used by EvaluationCache
```

### 2.3 Node Graph

**Architecture**: `Socket` → `Connection` → `BaseNode` → `NodeGraph`

**Socket types**: `IMAGE`, `MASK`, `VALUE`, `COLOR` (enum)

**Connection rules**: output→input only; same `SocketType` required (raises `ValueError`/`TypeError` on violation)

**Topological Sort**: Kahn's algorithm (BFS), detects cycles and raises `ValueError`

**Dirty Propagation**: BFS from dirty nodes through forward adjacency, marking all downstream nodes dirty

**Evaluation Flow**:
```
evaluate(force_all=False):
  1. force_all → mark all dirty
  2. _propagate_dirty() → BFS dirty marks downstream
  3. _topological_order() → Kahn sort
  4. For each node in order:
     if dirty → copy upstream socket values → node.evaluate() → mark_clean()
```

**Concrete Nodes**: `ImageInputNode`, `ImageOutputNode`, `ColorAdjustNode`, `BlendNode`

### 2.4 Legacy Adapter

`ProcessorNodeAdapter(BaseNode)` wraps any `BaseProcessor` as a `BaseNode`:
- `evaluate()` → `processor.process(img, props)` → first result to output socket, all to `_all_outputs`
- Multi-output support: splitters (custom_splitter, grid_splitter) return all cells

`ChainAsGraph.execute_chain()` — drop-in replacement for `CommandDispatcher.execute_chain()`:
```
1. Parse cmd_str → List[(op_name, props)]
2. Build linear NodeGraph: Input → Adapter₁ → ... → Adapterₙ → Output
3. graph.evaluate(force_all=True)
4. Collect: multi-output → all _all_outputs; single-output → output block
5. Clear all ImageDataBlocks; return safe copies
```

Pixel-identical to `CommandDispatcher` — verified by 15 integration tests.

### 2.5 Custom Splitter (Guide-Based Cutting)

The `custom_splitter` processor uses `ListProp` for arbitrary numbers of guide lines:

```
process(image, {h_lines: [100,300], v_lines: [200,400]}):
  y_points = sorted({0, h, 100, 300})  → [0, 100, 300, h]
  x_points = sorted({0, w, 200, 400})  → [0, 200, 400, w]
  
  For each rect in 3×3 grid: image.crop(...)
  Returns: len(y_points)-1 × len(x_points)-1 = 9 cells
```

No hardcoded limits — tested with up to 28 h-lines × 38 v-lines = 1131 cells.

---

## 3. Parameter Alignment Protocol

### 3.1 The Complete Flow

```
Source Layer              Raw Value       Type       Validated By
─────────────────────────────────────────────────────────────────
CLI --set rows=3           "3" (str)       int        config_coercion
GUI StringVar             "3" (str)       int        config_coercion
Script Engine             "3" (str)       int        config_coercion
Dispatcher.parse_command  ast.literal     int        ast node
config_coercion           returned int    int        _coerce_value()
config_model.__post_init__ validated      int        validate()
processor.process()       consumed        int        model guarantee
```

### 2.2 Supported Types and Coercion Rules

| UI Type | Python Type | Coercion Rule | Example |
|---------|------------|---------------|---------|
| `int` | `int` | `int(value)` | `"3"` → `3` |
| `float` | `float` | `float(value)` | `"2.5"` → `2.5` |
| `bool` | `bool` | `"true"/"1"/"yes"/"on"` → True | `"false"` → `False` |
| `list` | `list` | `ast.literal_eval(value)` | `"[1,2,3]"` → `[1,2,3]` |
| `enum` | `str` | Must be in `options` | `"JPEG"` ∈ `["WebP","JPEG","PNG","BMP"]` |
| `str` | `str` | Direct pass-through | `"hello"` → `"hello"` |

### 2.3 Config Model Validation Matrix

| Model | Validated Fields | Constraints |
|-------|-----------------|-------------|
| `SplitConfig` | rows, cols, offsets | `> 0` integers, 4-tuple non-negative |
| `AdjustConfig` | width, height | Auto-coerce string to int/float, `> 0` |
| `CustomSplitConfig` | h_lines, v_lines | Lists of non-negative integers |
| `ResizeConfig` | width, height | `> 0` floats |
| `GeometryConfig` | rotate | `int` in `{0, 90, 180, 270}` |
| `FormatConfig` | format, quality | `str` in `{WebP,JPEG,PNG,BMP}`, quality `[1,100]` |
| `WatermarkConfig` | size, opacity, anchor | size `> 0`, opacity `[0,255]`, anchor in `{TL,TR,BL,BR,C}` |
| `ColorConfig` | brightness, contrast, sharpness, color | No hard constraints (any float) |
| `FilterConfig` | grayscale, invert | Bool values only |
| `MetadataConfig` | strip_all, keep_icc | Bool values only |

### 2.4 Context Injection (Template Variables)

| Source | Variable | Type | Example |
|--------|----------|------|---------|
| `core.py` (system) | `{filename}` | `str` | `"photo"` |
| `core.py` (system) | `{index}` | `str` | `"01"` |
| `core.py` (system) | `{w}` | `int` | `300` |
| `core.py` (system) | `{h}` | `int` | `200` |
| `core.py` (system) | `{ext}` | `str` | `"png"` |
| `splitter.py` | `{row}` | `int` | `2` |
| `splitter.py` | `{col}` | `int` | `3` |
| `adjuster.py` | `{anchor}` | `str` | `"center"` |
| `watermark.py` | `{text}` | `str` | `"PROTOTYPE"` |
| `format_converter.py` | `{quality}` | `int` | `80` |

---

## 4. Module Contract

### 3.1 Processor Contract

Every processor MUST implement:

```python
class MyProcessor(BaseProcessor):
    @property
    def name(self) -> str: ...           # snake_case, unique
    @property
    def display_name(self) -> str: ...   # Human-readable, unique
    @property
    def category(self) -> str: ...       # Split|Transform|Edit|Filter|Export
    @property
    def tool_tip(self) -> str: ...       # Non-empty description
    def get_ui_metadata(self) -> List[Dict]: ...  # name, label, type, default
    def process(self, image, config) -> List[Tuple[Image, Dict]]: ...
    def draw_preview(self, canvas, ...) -> None: ...  # Optional overlay
```

### 3.2 Registry Contract

```python
ProcessorRegistry.register(processor)   # Idempotent, warns on duplicate
ProcessorRegistry.get(name)             # Raises ValueError if not found
ProcessorRegistry.list_all()            # Returns List[BaseProcessor]
ProcessorRegistry.reset()               # Clears all (test use only)
```

### 3.3 Dispatcher Contract

```python
CommandDispatcher.parse_command(cmd_str)    # → List[(name, {params})]
CommandDispatcher.execute_chain(img, cmd, extra_config=None)  # → List[Image]
```

---

## 5. Preventing Common Mistakes

### 4.1 Parameter Type Mismatch

**Problem**: CLI passes all values as strings, processor expects `int`.

**Solution**: `coerce_processor_config()` runs BEFORE `config_model.__post_init__()`:
```
CLI: --set rows=3          → "3" (str)
coerce:                    → 3 (int)
config_model:              → SplitConfig(rows=3) ✅
```

### 4.2 Hardcoded Processor Count

**Problem**: Tests break when adding/removing processors.

**Solution**: Use `>=` comparison or dynamic counting:
```python
# ❌ Bad
self.assertEqual(len(names), 11)

# ✅ Good
self.assertGreaterEqual(len(names), 11)
names = get_processor_names()  # From conftest
```

### 4.3 Font Platform Dependency

**Problem**: `arial.ttf` only exists on Windows.

**Solution**: Platform-aware font search with `_load_font()`:
```python
_FONT_SEARCH_PATHS = {
    "Windows": ["arial.ttf", "C:/Windows/Fonts/arial.ttf"],
    "Darwin": ["/System/Library/Fonts/Helvetica.ttc", ...],
    "Linux": ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", ...],
}
```

### 4.4 ICC Profile Loss

**Problem**: `img.crop()` strips the ICC profile from `img.info`.

**Solution**: Save `orig_icc_profile` before processing, restore in `save_args`:
```python
orig_icc_profile = orig_img.info.get('icc_profile')
# ... processing ...
icc_profile = context.get('icc_profile') or cell.info.get('icc_profile') or orig_icc_profile
if icc_profile:
    save_args['icc_profile'] = icc_profile
```

### 4.5 P-Mode Image Handling

**Problem**: `ImageOps.invert()` raises `OSError` on palette-mode images.

**Solution**: Convert P to RGB before invert:
```python
if img.mode == 'P':
    img = img.convert("RGB")
    img = ImageOps.invert(img)
```

### 4.6 GUI Thread Blocking

**Problem**: `process_image()` runs synchronously in main GUI thread.

**Solution**: All processing dispatched via `threading.Thread(daemon=True)`.

---

## 6. Test Methodology

### 5.1 Test Organization

```
tests/
├── conftest.py               # Shared fixtures (never hardcoded)
├── test_operator_compliance   # Architecture contract validation
├── test_config_coercion       # Type coercion unit tests
├── test_dispatcher            # Parsing + chaining + coercion
├── test_history               # Undo/redo stack
├── test_macro                 # Recording + playback
├── test_presets               # Save/load/list/import/export
├── test_plugin                # Plugin discovery + function
├── test_adjuster              # Canvas adjuster
├── test_custom_splitter       # Custom line splitting
├── test_edge_cases            # Boundary conditions per processor
├── test_error_paths           # Error handling paths
├── test_processors_expanded   # Deep tests (rounding, pixel accuracy)
├── test_save_compatibility    # Save/environment compatibility
├── test_workflow              # End-to-end integration chains
├── test_integration           # Pipeline integration tests
├── test_cli                   # CLI argument parsing + execution
├── test_gui_smoke             # GUI widget lifecycle
├── test_gui_workflows         # GUI full workflow
├── test_gui_param_sync        # GUI widget→state param sync
├── test_console_panel         # UI: interactive command console panel
├── test_pipeline_editor       # UI: visual pipeline chain editor
├── test_param_widgets         # UI: shared parameter widget factory
├── test_ui_preview            # Preview rendering
├── test_script_engine         # Script engine execution
├── test_settings              # Settings persistence
├── test_keymap                # Keybinding system
├── test_engine_v4             # Engine integrity
└── test_bug_fixes              # Regression tests (BUG-01 ~ BUG-40)
```

### 5.2 Running Tests

```bash
# Full suite (426 tests)
python -m pytest tests/ -v

# Non-GUI only (headless CI)
python -m pytest tests/ -v -k "not gui and not ui_preview"

# Single file
python -m pytest tests/test_workflow.py -v

# Type check
python -m mypy image_splitter --ignore-missing-imports
```

### 5.3 Adding a New Test

1. If testing a new processor → add to `test_processors_expanded.py` + compliance is automatic
2. If testing a workflow → add to `test_workflow.py`
3. If testing a bug fix → add to `test_bug_fixes.py`
4. Always inherit from `BaseTest` (in conftest.py) for standard fixtures
5. Never hardcode processor counts — use `processor_count()` or `assertGreaterEqual()`

### 5.4 Test-Suite Optimization (V12.0)

The V12.0 cycle consolidated the suite via shared helpers and duplicate removal while
adding P0 UI component coverage:

| Optimization | Description |
|--------------|-------------|
| **TkTestCase base** | Shared `TkTestCase` base class centralizes customtkinter teardown/destroy logic across UI tests |
| **CLI `run_cli` helper** | Single `run_cli(args)` helper replaces per-test `subprocess`/`argv` boilerplate in `test_cli.py` |
| **`assert_images_equal` helper** | Shared pixel-equality assertion consolidates ad-hoc `ImageChops.difference` + `getbbox` checks |
| **`make_rgb_image` deduplication** | Centralized RGB test-image factory removes duplicated fixture builders |
| **ChainAsGraph equivalence dedup** | 3 redundant equivalence tests removed, 2 unique variants retained — same coverage, less duplication |
| **CommandDispatcher delegation guard** | Guard test verifies `CommandDispatcher.execute_chain()` delegates to `ChainAsGraph` (single execution path) |

**P0 UI component coverage added** (18 targeted tests):

| File | Coverage |
|------|----------|
| `test_param_widgets.py` | Shared parameter widget factory — all widget types + coercion |
| `test_console_panel.py` | Interactive command console — submit, history, tab completion |
| `test_pipeline_editor.py` | Visual pipeline chain editor — add/remove/reorder nodes |
| `test_gui_param_sync.py` | GUI widget→state data flow — parameter synchronization |

**Result**: 426 passed, 37 test files, 83 source files (mypy clean).

---

## 7. CI/CD Pipeline

### 6.1 Workflow (`ci.yml`)

```
on: push/pull_request to main/master

jobs:
  test:
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
        python-version: [3.10, 3.11, 3.12, 3.13]
    steps:
      - checkout
      - setup-python
      - pip install -e ".[dev]"
      - pytest (non-GUI) + mypy + ruff

  coverage:
    runs-on: ubuntu-latest
    steps:
      - pytest --cov --cov-report=xml
      - codecov upload
```

### 6.2 Quality Gates

| Gate | Command | Threshold |
|------|---------|-----------|
| Tests | `pytest tests/ -v` | 100% pass |
| Types | `mypy image_splitter --ignore-missing-imports` | 0 errors |
| Lint | `ruff check image_splitter/` | 0 errors |

---

## 8. Version History

| Version | Date | Highlights |
|---------|------|------------|
| V5.5 | 2026-05 | Google Python Style compliance |
| V6.0 | 2026-05 | 22 bug fixes, 147 tests |
| V7.0 | 2026-05 | History, macro, console, plugin system (176 tests) |
| V9.0 | 2026-06 | mypy 0 errors, presets, pipeline editor, CI/CD, ChainAsGraph pixel-identical tests, 405 tests, 33 files |
| V12.0 | 2026-06-26 | **Current** — test-suite optimization (shared helpers, duplicate consolidation, delegation guard), P0 UI component test coverage, 426 tests, 37 files, mypy 0 errors (83 source files) |
