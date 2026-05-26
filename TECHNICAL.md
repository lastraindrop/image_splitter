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

## 2. Parameter Alignment Protocol

### 2.1 The Complete Flow

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

## 3. Module Contract

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

## 4. Preventing Common Mistakes

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

## 5. Test Methodology

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
├── test_ui_preview            # Preview rendering
├── test_script_engine         # Script engine execution
├── test_settings              # Settings persistence
├── test_keymap                # Keybinding system
├── test_engine_v4             # Engine integrity
└── test_bug_fixes              # Regression tests (BUG-01 ~ BUG-40)
```

### 5.2 Running Tests

```bash
# Full suite (218 tests)
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

---

## 6. CI/CD Pipeline

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

## 7. Version History

| Version | Date | Highlights |
|---------|------|------------|
| V5.5 | 2026-05 | Google Python Style compliance |
| V6.0 | 2026-05 | 22 bug fixes, 147 tests |
| V7.0 | 2026-05 | History, macro, console, plugin system (176 tests) |
| V8.0 | 2026-05 | **Current** — mypy 0 errors, presets, pipeline editor, CI/CD, 218 tests, 25 files |
