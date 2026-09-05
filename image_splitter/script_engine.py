"""Simple script engine for batch processing."""
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image

from image_splitter.core import process_image, register_all_processors
from image_splitter.engine.registry import ProcessorRegistry


class ScriptResult:
    """Script execution result."""

    def __init__(self, success: bool, message: str, output_files: Optional[List[Path]] = None):
        self.success = success
        self.message = message
        self.output_files: List[Path] = output_files or []


def chain_output_spec(chain_spec: str) -> tuple[str, dict[str, Any]]:
    """Derive the output extension and save kwargs for a chain.

    If the *last* operator in the chain is ``format_converter`` the chain
    output honours its target format and quality; otherwise the output
    defaults to PNG.  This closes known limitation L-3 (chain output was
    previously hard-coded to ``.png`` regardless of a trailing converter).
    """
    from image_splitter.engine.config_coercion import coerce_processor_config
    from image_splitter.engine.dispatcher import CommandDispatcher

    ext = "png"
    save_kwargs: dict[str, Any] = {}
    try:
        ops = CommandDispatcher.parse_command(chain_spec)
    except ValueError:
        return ext, save_kwargs
    if not ops:
        return ext, save_kwargs

    last_name, last_props = ops[-1]
    if last_name != "format_converter":
        return ext, save_kwargs

    if not ProcessorRegistry.list_all():
        from image_splitter.core import register_all_processors
        register_all_processors()
    processor = ProcessorRegistry.get("format_converter")
    coerced = coerce_processor_config(processor, dict(last_props))
    fmt = str(coerced.get("format", "WebP"))
    quality = int(coerced.get("quality", 80))
    ext_map = {"WebP": "webp", "JPEG": "jpg", "PNG": "png", "BMP": "bmp"}
    ext = ext_map.get(fmt, "png")
    if fmt in ("JPEG", "WebP"):  # quality only for lossy formats
        save_kwargs["quality"] = quality
    return ext, save_kwargs


class ScriptEngine:
    """Simple script engine for batch processing."""

    def __init__(self) -> None:
        register_all_processors()

    def get_available_operators(self) -> List[str]:
        """Get list of available operator names."""
        return [p.name for p in ProcessorRegistry.list_all()]

    def process(
        self,
        input_files: List[str],
        operator: str,
        config: Dict[str, Any]
    ) -> ScriptResult:
        """Process files with an operator."""
        try:
            ProcessorRegistry.get(operator)
        except ValueError:
            return ScriptResult(False, f"Unknown operator: {operator}")

        output_dir = config.get("output_dir", "./output")
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        success_count = 0
        output_files: List[Path] = []
        out_dir = Path(output_dir)

        for path in input_files:
            before = set(out_dir.glob("*")) if out_dir.exists() else set()
            success, msg = process_image(path, operator, config)
            if success:
                success_count += 1
                after = set(out_dir.glob("*")) if out_dir.exists() else set()
                output_files.extend(after - before)

        return ScriptResult(
            success_count > 0,
            f"Processed {success_count}/{len(input_files)} files",
            output_files
        )

    def chain(
        self,
        input_paths: List[str],
        chain_spec: str,
        output_dir: str = "./output"
    ) -> ScriptResult:
        """Execute a chain of operators.

        Example: chain_spec = "resizer(width=0.5)|grid_splitter(rows=2,cols=2)"

        Uses ChainAsGraph (Node Graph engine) for consistent execution
        across GUI and CLI pipelines.
        """
        from image_splitter.core import _prepare_image_for_save
        from image_splitter.engine.legacy_adapter import ChainAsGraph

        Path(output_dir).mkdir(parents=True, exist_ok=True)
        out_ext, save_kwargs = chain_output_spec(chain_spec)
        ext_format = {"webp": "WEBP", "jpg": "JPEG", "jpeg": "JPEG",
                      "png": "PNG", "bmp": "BMP"}
        save_fmt = ext_format.get(out_ext, "PNG")

        results = []
        output_files = []
        idx = 1

        for path in input_paths:
            with Image.open(path) as img:
                try:
                    # V14-8: preserve the source ICC profile —
                    # core.process_image keeps it but the chain path
                    # previously dropped it, producing desaturated
                    # output on wide-gamut displays.
                    icc_profile = img.info.get("icc_profile")
                    processed = ChainAsGraph.execute_chain(img, chain_spec)
                    stem = Path(path).stem
                    save_kwargs_file = dict(save_kwargs)
                    if icc_profile:
                        save_kwargs_file["icc_profile"] = icc_profile
                    for proc_img in processed:
                        out_path = Path(output_dir) / f"{stem}_chain_{idx:02d}.{out_ext}"
                        save_img = _prepare_image_for_save(proc_img, save_fmt)
                        try:
                            save_img.save(out_path, **save_kwargs_file)
                        finally:
                            if save_img is not proc_img:
                                save_img.close()
                        output_files.append(out_path)
                        proc_img.close()
                        idx += 1
                    results.append((path, True, "Success"))
                except Exception as e:
                    results.append((path, False, str(e)))

        success_count = sum(1 for _, s, _ in results if s)

        # Surface the first failure reason so CLI users see *why* the chain
        # failed instead of an opaque "0/N" count.
        detail = ""
        failed = [msg for _, s, msg in results if not s]
        if failed and success_count == 0:
            detail = f" — {failed[0]}"

        return ScriptResult(
            success_count > 0,
            f"Chain processed {success_count}/{len(input_paths)} files{detail}",
            output_files
        )

    def batch_script(
        self,
        script_path: str,
        input_files: List[str],
        output_dir: str = "./output"
    ) -> ScriptResult:
        """Execute a script file."""
        if not os.path.exists(script_path):
            return ScriptResult(False, f"Script file not found: {script_path}")

        with open(script_path, "r", encoding="utf-8") as f:
            script_content = f.read()

        return self.execute_script(script_content, input_files, output_dir)

    def execute_script(
        self,
        script_content: str,
        input_files: List[str],
        output_dir: str = "./output"
    ) -> ScriptResult:
        """Execute script content.

        Script format:
            # Comment line
            operator_name param1=value1 param2=value2
        """
        lines = script_content.strip().split("\n")
        results = []

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split()
            if not parts:
                continue

            operator = parts[0]
            config = {"output_dir": output_dir}

            for param in parts[1:]:
                if "=" in param:
                    key, value = param.split("=", 1)
                    config[key] = value

            result = self.process(input_files, operator, config)
            results.append(result)

        success_count = sum(1 for r in results if r.success)

        return ScriptResult(
            success_count > 0,
            f"Script executed: {success_count}/{len(results)} operators",
            []
        )


def run_script_file(script_path: str, input_files: List[str], output_dir: str = "./output") -> ScriptResult:
    """Convenience function to run a script file."""
    engine = ScriptEngine()
    return engine.batch_script(script_path, input_files, output_dir)


def run_chain(chain_spec: str, input_files: List[str], output_dir: str = "./output") -> ScriptResult:
    """Convenience function to run a chain spec."""
    engine = ScriptEngine()
    return engine.chain(input_files, chain_spec, output_dir)