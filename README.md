# Image Splitter Pro

A lightweight, modular image processing framework with Blender-like operator philosophy. Supports grid splitting, custom line cutting, resizing, canvas adjustment, and more.

## Features

### Core Philosophy
- **Everything as Operators**: Complete decoupling between core logic and UI. Supports Blender-style operator invocation logs and command dispatching.
- **Metadata-Driven UI**: GUI automatically generates parameter panels based on processor metadata. Adding new features only requires implementing a plugin.
- **High-Performance Engine**: CLI version uses multi-processing by default, delivering 4-8x performance improvement.
- **Industrial-Grade Safety**: Strict Pillow handle management with Path Traversal interception.
- **Custom Line Cutting**: Supports arbitrary pixel positions for horizontal/vertical splitting.
- **Advanced Canvas Adjustment**: Support for padding, cropping, and custom background colors.

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
        "<Control-Enter>": "run_batch",
        "<Delete>": "remove_selected"
    }
}
```

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
├── pyproject.toml         # Package configuration
├── engine/
│   ├── base.py             # BaseProcessor/BaseConfig abstract classes
│   ├── registry.py         # Processor registration center
│   ├── dispatcher.py       # Command dispatcher for chaining
│   └── config_coercion.py  # Parameter type coercion
├── processors/             # Processor plugins (10 total)
├── models.py               # Configuration dataclasses
└── tests/                 # Test suite (69 tests)
```

## Requirements

- Python 3.10+
- Pillow 10.2.0+

## License

MIT