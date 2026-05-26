# Image Splitter Pro

A lightweight, modular image processing framework with Blender-like operator philosophy. Supports grid splitting, custom line cutting, resizing, canvas adjustment, and more.

## Features

### Core Philosophy
- **Everything as Operators**: Complete decoupling between core logic and UI. Blender-style operator invocation logs and command dispatching.
- **Metadata-Driven UI**: GUI auto-generates parameter panels from processor metadata. New features = drop-in plugin.
- **Operation History**: Undo/Redo stack records every operation, exportable as JSON log.
- **Macro Recording**: One-click recording generates reusable Python scripts.
- **Parameter Presets**: Save/load named parameter presets per operator (CLI `--preset` and GUI).
- **Visual Pipeline Editor**: Compose multi-step operator chains via GUI (Ctrl+P).
- **Interactive Console**: Built-in command console with tab completion and history (Ctrl+`).
- **Plugin System**: Drop a `BaseProcessor` subclass in `plugins/` and it's auto-discovered.
- **High-Performance Engine**: CLI version uses multi-processing by default (4-8x speedup).
- **Industrial-Grade Safety**: Strict Pillow handle management with Path Traversal interception.
- **Cross-Platform**: Full Windows/macOS/Linux support with platform-aware font loading.
- **Static Type Checking**: Full mypy compliance — zero type errors.

## Quick Start

### Installation

```bash
pip install -e .
```

### GUI Mode

```bash
python -m image_splitter.gui
# or
image-splitter-gui
```

### CLI Mode

```bash
# Split test.png into 3x3 grid with 8 parallel processes
python -m image_splitter.cli test.png -r 3 -c 3 -o ./output -j 8

# Use a saved preset
python -m image_splitter.cli input.png --preset "my_split"

# Save current parameters as a preset
python -m image_splitter.cli input.png -r 3 -c 3 --preset-save "3x3_grid"

# List saved presets
python -m image_splitter.cli input.png --preset-list
```

### Script Mode

```bash
# Execute script file
python -m image_splitter.cli input.png -s script.txt

# Chain operations
python -m image_splitter.cli input.png --chain "resizer(width=0.5)|grid_splitter(rows=2,cols=2)"
```

## Available Processors

| Processor | Description |
|-----------|-------------|
| `grid_splitter` | Split image into uniform grid (rows x cols) |
| `custom_splitter` | Custom coordinate-based splitting |
| `resizer` | Proportional image scaling |
| `canvas_adjuster` | Canvas padding, cropping, background fill |
| `format_converter` | WebP/JPEG/PNG/BMP format conversion with quality control |
| `geometry` | Rotation (90/180/270) and flip operations |
| `filters` | Grayscale and invert filters |
| `color_adjuster` | Brightness, contrast, sharpness, saturation tuning |
| `metadata_cleaner` | Strip EXIF/GPS privacy data |
| `text_watermark` | Add semi-transparent text watermark |

## Template Placeholders

| Placeholder | Description |
|-------------|-------------|
| `{filename}` | Original filename without extension |
| `{row}` / `{col}` | Current row/column number (1-based) |
| `{index}` | Global sequence number (01-based, zero-padded) |
| `{w}` | Processed image width in pixels |
| `{h}` | Processed image height in pixels |
| `{ext}` | File extension |
| `{anchor}` | Anchor position (TL, TR, BL, BR, C) |
| `{text}` | Watermark text content |
| `{quality}` | Export quality parameter |

## Configuration

Settings are persisted to `~/.image_splitter/settings.json`:

```json
{
    "output_dir": "./output",
    "default_processor": "grid_splitter",
    "template": "{filename}_{index}",
    "max_workers": 0,
    "default_rows": 3,
    "default_cols": 3
}
```

## Keybindings

Default keybindings in `~/.image_splitter/keymap.json`:

```json
{
    "global": {
        "<Control-o>": "select_files",
        "<Control-Return>": "run_batch",
        "<Delete>": "remove_selected"
    }
}
```

| Shortcut | Action |
|----------|--------|
| `Ctrl+O` | Open images |
| `Ctrl+Enter` | Run batch processing |
| `Delete` | Remove selected file |
| `Ctrl+P` | Toggle pipeline editor |
| `Ctrl+Shift+R` | Start/stop macro recording |
| `Ctrl+Z` | Undo last operation |
| `Ctrl+Shift+Z` | Redo last operation |
| `` Ctrl+` `` | Toggle command console |

## Development

This project supports plugin development. Simply inherit from `BaseProcessor` and implement your logic to automatically get CLI support and GUI panel generation.

See [DEVELOPER.md](./DEVELOPER.md) for details and [TECHNICAL.md](./TECHNICAL.md) for a comprehensive technical guide.

## Architecture

```
image_splitter/
├── cli.py                    # CLI entry point (multiprocessing)
├── gui.py                    # GUI entry point (threaded)
├── core.py                   # Core processing pipeline + auto-discovery
├── settings.py               # User settings persistence
├── keymap.py                 # Keybinding system
├── script_engine.py          # Batch scripting engine
├── logging_config.py         # Logging configuration
├── models.py                 # Configuration dataclasses (10 models)
├── pyproject.toml            # Package configuration
├── engine/
│   ├── base.py               # BaseProcessor/BaseConfig abstract classes
│   ├── registry.py           # Processor registry (singleton + duplicate detection)
│   ├── dispatcher.py         # Command dispatcher + chain execution
│   ├── config_coercion.py    # Parameter type coercion
│   ├── history.py            # Operation history stack (undo/redo)
│   ├── macro.py              # Macro recording & playback
│   └── presets.py            # Parameter presets (save/load/import/export)
├── processors/               # Processor plugins (10 built-in)
├── plugins/                  # User plugin directory (auto-discovered)
│   └── example_plugin.py     # Example: invert colors plugin
├── ui/
│   ├── console.py            # Interactive command console panel
│   └── pipeline.py           # Visual pipeline chain editor
├── .github/workflows/
│   └── ci.yml                # CI/CD pipeline (multi-OS, Python 3.10-3.13)
└── tests/                    # Test suite (218 tests, 25 files)
```

## Requirements

- Python 3.10+
- Pillow 10.2.0+

## License

MIT

## Test Suite

The project includes **218 tests** across 25 test files:

| Test File | Description |
|-----------|-------------|
| `conftest.py` | Shared fixtures: BaseTest, test images, color constants |
| `test_adjuster.py` | Canvas adjuster: padding, cropping, ratio, fail-fast validation |
| `test_bug_fixes.py` | Regression tests for all confirmed bug fixes (30 tests) |
| `test_cli.py` | CLI mode: basic flow, recursive discovery, concurrency, error handling |
| `test_config_coercion.py` | Parameter type coercion for all supported types |
| `test_custom_splitter.py` | Custom line splitter: simple, irregular, out-of-bounds, negative rejection |
| `test_dispatcher.py` | Command parsing + chain execution with coercion and extra_config |
| `test_edge_cases.py` | Edge case tests for all processors: 1x1, tiny ratios, empty text, P-mode |
| `test_engine_v4.py` | Registry integrity, processor smoke test, path security, format adaptation |
| `test_error_paths.py` | Error handling: missing files, invalid templates, bad enum/list values |
| `test_gui_smoke.py` | GUI initialization, file selection, processor switching, stop/cancel |
| `test_gui_workflows.py` | GUI workflow: full parameter coercion and batch run verification |
| `test_history.py` | History system: push, undo, redo, clear, max-depth, export log |
| `test_integration.py` | End-to-end: full pipeline, RGBA/L-mode smoke, CLI chain, template vars |
| `test_keymap.py` | Keybinding: bind/unbind/lookup, import/export, reset, multiple contexts |
| `test_macro.py` | Macro recording: record, stop, generate script, playback, save |
| `test_operator_compliance.py` | Compliance audit + parameter contract for all processors |
| `test_plugin.py` | Plugin system: auto-discovery, metadata, functional inversion |
| `test_presets.py` | Presets: save/load/list/delete/export/import + CLI integration (14 tests) |
| `test_processors_expanded.py` | Deep: rounding consistency, watermark positioning, pixel accuracy, stress |
| `test_save_compatibility.py` | Save: ICC profile preservation, format conversion extension changes |
| `test_script_engine.py` | Script engine: process, chain, batch script, error handling, operators list |
| `test_settings.py` | Settings: defaults, save/load roundtrip, merge, get/set, corrupted JSON |
| `test_ui_preview.py` | Preview rendering: all processor draw_preview, graceful dirty-data handling |
| `test_workflow.py` | Full end-to-end workflows: chains, batch, presets+macro+history, boundary values |

Run tests:
```bash
# Full suite
python -m pytest tests/ -v

# Non-GUI only (for CI)
python -m pytest tests/ -v -k "not gui and not ui_preview"

# Type check
python -m mypy image_splitter --ignore-missing-imports
```
