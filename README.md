# Image Splitter Pro

A lightweight, modular image processing framework with Blender-like operator philosophy. Supports grid splitting, custom line cutting, resizing, canvas adjustment, and more.

## Features

### Core Philosophy
- **Everything as Operators**: Complete decoupling between core logic and UI. Supports Blender-style operator invocation logs and command dispatching.
- **Metadata-Driven UI**: GUI automatically generates parameter panels based on processor metadata. Adding new features only requires implementing a plugin.
- **Operation History**: Undo/Redo stack records every operation, exportable as JSON log.
- **Macro Recording**: One-click recording generates reusable Python scripts.
- **Interactive Console**: Built-in command console with tab completion and history.
- **Plugin System**: Drop a `BaseProcessor` subclass in `plugins/` and it's auto-discovered.
- **High-Performance Engine**: CLI version uses multi-processing by default, delivering 4-8x performance improvement.
- **Industrial-Grade Safety**: Strict Pillow handle management with Path Traversal interception.

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
| `format_converter` | WebP/JPEG/PNG format conversion with quality control |
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

Settings are persisted to `~/.image_splitter/settings.json`. You can customize:

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

Default keybindings are stored in `~/.image_splitter/keymap.json`:

```json
{
    "global": {
        "<Control-o>": "select_files",
        "<Control-Return>": "run_batch",
        "<Delete>": "remove_selected"
    }
}
```

Built-in shortcuts (always available):

| Shortcut | Action |
|----------|--------|
| `Ctrl+O` | Open images |
| `Ctrl+Enter` | Run batch processing |
| `Delete` | Remove selected file |
| `Ctrl+Shift+R` | Start/stop macro recording |
| `Ctrl+Z` | Undo last operation |
| `Ctrl+Shift+Z` | Redo last operation |
| `` Ctrl+` `` | Toggle command console |

## Development

This project supports plugin development. Simply inherit from `BaseProcessor` and implement your logic to automatically get CLI support and GUI panel generation.

See [DEVELOPER.md](./DEVELOPER.md) for details.

## Architecture

```
image_splitter/
├── cli.py                    # CLI entry point
├── gui.py                    # GUI entry point  
├── core.py                  # Core processing pipeline
├── settings.py              # User settings persistence
├── keymap.py               # Keybinding system
├── script_engine.py         # Batch scripting engine
├── logging_config.py       # Logging configuration
├── models.py               # Configuration dataclasses
├── pyproject.toml         # Package configuration
├── engine/
│   ├── base.py             # BaseProcessor/BaseConfig abstract classes
│   ├── registry.py         # Processor registration center
│   ├── dispatcher.py       # Command dispatcher for chaining
│   ├── config_coercion.py  # Parameter type coercion
│   ├── history.py          # Operation history stack (undo/redo)
│   └── macro.py            # Macro recording & playback
├── processors/             # Processor plugins (10 built-in)
├── plugins/                # User plugin directory (auto-discovered)
│   └── example_plugin.py   # Example: invert colors plugin
├── ui/
│   ├── __init__.py
│   └── console.py          # Interactive command console panel
└── tests/                 # Test suite (176 tests)
```

## Requirements

- Python 3.10+
- Pillow 10.2.0+

## License

MIT

## Test Suite

The project includes 176 tests across 23 test files:

| Test File | Description |
|-----------|-------------|
| `test_adjuster.py` | Canvas adjuster: padding, cropping, ratio, fail-fast validation |
| `test_bug_fixes.py` | Regression tests for all confirmed bug fixes (21 tests) |
| `test_cli.py` | CLI mode: basic flow, recursive discovery, concurrency, error handling |
| `test_config_coercion.py` | Parameter type coercion for all supported types |
| `test_custom_splitter.py` | Custom line splitter: simple, irregular, out-of-bounds, negative rejection |
| `test_dispatcher.py` | Command parsing: simple, complex literals, chain execution |
| `test_dispatcher_coercion.py` | Type coercion in dispatch: defaults, strings, complex chains |
| `test_edge_cases.py` | Edge case tests for all processors: 1x1, tiny ratios, empty text, P-mode |
| `test_engine_v4.py` | Registry integrity, processor smoke test, path security, format adaptation |
| `test_error_paths.py` | Error handling: missing files, invalid templates, bad enum/list values |
| `test_gui_smoke.py` | GUI initialization, file selection, processor switching, stop/cancel |
| `test_gui_workflows.py` | GUI workflow: full parameter coercion and batch run verification |
| `test_history.py` | History system: push, undo, redo, clear, max-depth, export log |
| `test_integration.py` | End-to-end: full pipeline, RGBA/L-mode smoke, CLI chain, template vars |
| `test_keymap.py` | Keybinding: bind/unbind/lookup, import/export, reset, multiple contexts |
| `test_macro.py` | Macro recording: record, stop, generate script, playback, save |
| `test_operator_compliance.py` | Compliance audit: naming, metadata schema, category, GUI addressability |
| `test_parameter_contract.py` | Parameter contract: metadata completeness, coercion type matching |
| `test_plugin.py` | Plugin system: auto-discovery, example plugin metadata, processing |
| `test_processors_expanded.py` | Deep: rounding consistency, watermark positioning, pixel accuracy, stress test |
| `test_save_compatibility.py` | Save: ICC profile preservation, format conversion extension changes |
| `test_script_engine.py` | Script engine: process, chain, batch script, error handling, operators list |
| `test_settings.py` | Settings: defaults, save/load roundtrip, merge, get/set, corrupted JSON |
| `test_ui_preview.py` | Preview rendering: all processor draw_preview, graceful dirty-data handling |