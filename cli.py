# image_splitter/cli.py
"""Command-line interface for Image Splitter Pro."""
import argparse
import glob
import multiprocessing
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Tuple

# ---------------------------------------------------------
# Path self-fix: supports absolute import of image_splitter
# ---------------------------------------------------------
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from image_splitter import script_engine, settings
from image_splitter.core import process_image, register_all_processors
from image_splitter.engine.config_coercion import coerce_processor_config
from image_splitter.engine.registry import ProcessorRegistry


def _positive_int(value: str) -> int:
    """Parse and validate a positive integer argument."""
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("Must be an integer greater than 0")
    return parsed


def _parse_set_option(raw: str) -> Tuple[str, str]:
    """Parse a --set key=value option string."""
    if "=" not in raw:
        raise argparse.ArgumentTypeError("--set must use key=value format")
    key, value = raw.split("=", 1)
    key = key.strip()
    if not key:
        raise argparse.ArgumentTypeError("--set key cannot be empty")
    return key, value


def main() -> None:
    """CLI entry point: parse arguments and dispatch processing."""
    # Load settings
    loaded_settings = settings.load_settings()

    parser = argparse.ArgumentParser(
        description="Universal Image Processing Tool (CLI Version)"
    )

    # Core parameters
    parser.add_argument(
        "input",
        help="Input file, directory, or wildcard path (e.g., ./pics/*.png)"
    )
    parser.add_argument(
        "-o", "--output",
        default=loaded_settings.get("output_dir", "./output"),
        help="Output directory (default: read from settings or ./output)"
    )
    parser.add_argument(
        "-p", "--processor",
        default=loaded_settings.get("default_processor", "grid_splitter"),
        help="Processor name (default: read from settings or grid_splitter)"
    )
    parser.add_argument(
        "--set", dest="set_items", action="append", default=[], type=_parse_set_option,
        help="Processor parameters, format key=value, can be passed multiple times"
    )

    # Grid splitting compatible parameters (preserve legacy experience)
    default_rows = loaded_settings.get("default_rows", 3)
    default_cols = loaded_settings.get("default_cols", 3)
    parser.add_argument(
        "-r", "--rows", type=_positive_int,
        help=f"Number of rows for grid splitting (default: {default_rows})"
    )
    parser.add_argument(
        "-c", "--cols", type=_positive_int,
        help=f"Number of columns for grid splitting (default: {default_cols})"
    )

    # Advanced parameters
    parser.add_argument(
        "--offset", type=int, nargs=4, default=[0, 0, 0, 0],
        help="Edge offset: Left Top Right Bottom (pixels)"
    )
    parser.add_argument(
        "-t", "--template",
        default=loaded_settings.get("template", "{filename}_{index}"),
        help="Output filename template (default: read from settings)"
    )
    max_workers = loaded_settings.get("max_workers", 0)
    parser.add_argument(
        "-j", "--jobs", type=_positive_int,
        default=max_workers if max_workers > 0 else multiprocessing.cpu_count(),
        help="Number of parallel processes (default: CPU core count)"
    )
    parser.add_argument(
        "--recursive", action="store_true",
        help="Whether to search subdirectories recursively"
    )

    # Script parameters
    parser.add_argument(
        "-s", "--script", metavar="FILE",
        help="Script file path"
    )
    parser.add_argument(
        "--chain", metavar="SPEC",
        help="Chained operation spec, e.g., "
             "'resizer(width=0.5)|grid_splitter(rows=2,cols=2)'"
    )

    args = parser.parse_args()

    register_all_processors()
    processor = None
    try:
        processor = ProcessorRegistry.get(args.processor)
    except ValueError:
        print(f"[FAIL] Processor not found: {args.processor}")
        available = ", ".join(p.name for p in ProcessorRegistry.list_all())
        print(f"[INFO] Available processors: {available}")
        sys.exit(1)

    # 1. Resolve output directory
    output_dir = Path(args.output).resolve()

    # Script/Chain processing mode
    if args.script:
        engine = script_engine.ScriptEngine()
        result = engine.batch_script(args.script, [str(Path(args.input).resolve())], str(output_dir))
        print(f"[{'OK' if result.success else 'FAIL'}] {result.message}")
        sys.exit(0 if result.success else 1)

    if args.chain:
        engine = script_engine.ScriptEngine()
        result = engine.chain([str(Path(args.input).resolve())], args.chain, str(output_dir))
        print(f"[{'OK' if result.success else 'FAIL'}] {result.message}")
        sys.exit(0 if result.success else 1)

    # 2. Environment check and input parsing
    input_files = []
    
    # Allowed extensions
    exts = ["jpg", "jpeg", "png", "bmp", "webp"]
    
    # First check if it is a directory/file that exists directly
    p = Path(args.input)
    if p.is_dir():
        pattern = "**/*" if args.recursive else "*"
        for ext in exts:
            input_files.extend(p.glob(f"{pattern}.{ext}"))
            input_files.extend(p.glob(f"{pattern}.{ext.upper()}"))
    elif p.is_file():
        input_files.append(p)
    else:
        # Try wildcard parsing
        glob_matches = glob.glob(args.input, recursive=args.recursive)
        for g in glob_matches:
            gp = Path(g)
            if gp.is_file():
                if gp.suffix.lower().lstrip('.') in exts:
                    input_files.append(gp)
            elif gp.is_dir() and args.recursive:
                 for ext in exts:
                    input_files.extend(gp.glob(f"**/*.{ext}"))
                    input_files.extend(gp.glob(f"**/*.{ext.upper()}"))

    # Deduplicate and sort
    input_files = sorted(list(set(input_files)))

    # Filter out files in the output directory and its subdirectories
    # (prevent infinite loops)
    try:
        input_files = [
            f for f in input_files
            if not f.resolve().is_relative_to(output_dir)
        ]
    except ValueError:
        pass

    if not input_files:
        print(f"[INFO] No valid image files found: {args.input}")
        sys.exit(1)

    print(
        f"[INFO] Preparing to process {len(input_files)} file(s) "
        f"(concurrency: {args.jobs})...\n"
    )

    total_success = 0

    config = {k: v for k, v in args.set_items}
    if args.rows is not None:
        config["rows"] = args.rows
    if args.cols is not None:
        config["cols"] = args.cols
    if args.offset != [0, 0, 0, 0]:
        config["offsets"] = tuple(args.offset)

    config["output_dir"] = str(output_dir)
    config["template"] = args.template

    # BUG-06 Fix: Coerce types for --set parameters
    raw_config = config.copy()
    try:
        coerced_config = coerce_processor_config(processor, raw_config)
        config = coerced_config
    except ValueError as e:
        print(f"[FAIL] Parameter configuration error: {e}")
        sys.exit(1)

    if args.processor == "grid_splitter":
        if "rows" not in config:
            config["rows"] = 3
        if "cols" not in config:
            config["cols"] = 3
        if "offsets" not in config:
            config["offsets"] = tuple(args.offset)

    # 2. Parallel processing
    with ProcessPoolExecutor(max_workers=args.jobs) as executor:
        futures = [
            executor.submit(process_image, str(f), processor.name, config)
            for f in input_files
        ]

        for f_path, future in zip(input_files, futures):
            try:
                success, msg = future.result()
                status = "[OK]" if success else "[FAIL]"
                print(f"{status} {f_path.name}: {msg}")
                if success:
                    total_success += 1
            except Exception as e:
                print(f"[FAIL] {f_path.name}: Runtime exception - {e}")

    print("-" * 30)
    print(
        f"[DONE] Completed! Success: {total_success} / Total: {len(input_files)}"
    )
    
    if total_success < len(input_files):
        sys.exit(1)

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
