# image_splitter/script_engine.py
"""Simple script engine for batch processing."""
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image

from image_splitter.core import process_image, register_all_processors
from image_splitter.engine.dispatcher import CommandDispatcher
from image_splitter.engine.registry import ProcessorRegistry


class ScriptResult:
    """Script execution result."""

    def __init__(self, success: bool, message: str, output_files: Optional[List[Path]] = None):
        self.success = success
        self.message = message
        self.output_files: List[Path] = output_files or []


class ScriptEngine:
    """Simple script engine for batch processing."""

    def __init__(self):
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
        output_files = []

        for path in input_files:
            success, msg = process_image(path, operator, config)
            if success:
                success_count += 1
                # Collect output files
                out_dir = Path(output_dir)
                output_files.extend(out_dir.glob("*"))

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
        """
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        results = []
        output_files = []
        idx = 1

        for path in input_paths:
            with Image.open(path) as img:
                try:
                    processed = CommandDispatcher.execute_chain(img, chain_spec)
                    for proc_img in processed:
                        stem = Path(path).stem
                        out_path = Path(output_dir) / f"{stem}_chain_{idx:02d}.png"
                        proc_img.save(out_path)
                        output_files.append(out_path)
                        proc_img.close()
                        idx += 1
                    results.append((path, True, "Success"))
                except Exception as e:
                    results.append((path, False, str(e)))

        success_count = sum(1 for _, s, _ in results if s)

        return ScriptResult(
            success_count > 0,
            f"Chain processed {success_count}/{len(input_paths)} files",
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