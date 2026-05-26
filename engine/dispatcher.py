"""Command parsing and chained dispatching for operators."""
import ast

from typing import Any, Dict, List, Tuple

from PIL import Image

from image_splitter.engine.config_coercion import coerce_processor_config
from image_splitter.engine.registry import ProcessorRegistry

class CommandDispatcher:
    """
    Blender-style command parsing and dispatch center
    """

    @staticmethod
    def _parse_operator_token(token: str) -> Tuple[str, Dict[str, Any]]:
        try:
            node = ast.parse(token, mode="eval").body
        except SyntaxError as exc:
            raise ValueError(f"Invalid command syntax: {token}") from exc

        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            raise ValueError(f"Invalid operator syntax: {token}")
        if node.args:
            raise ValueError(f"Currently only keyword arguments are supported: {token}")

        props: Dict[str, Any] = {}
        for keyword in node.keywords:
            if keyword.arg is None:
                raise ValueError(f"Argument unpacking syntax is not supported: {token}")
            try:
                props[keyword.arg] = ast.literal_eval(keyword.value)
            except (ValueError, SyntaxError) as exc:
                raise ValueError(f"Value of parameter '{keyword.arg}' cannot be parsed: {token}") from exc

        return node.func.id, props

    @classmethod
    def parse_command(cls, cmd_str: str) -> List[Tuple[str, Dict[str, Any]]]:
        """Parse a command string into a list of (operator_name, props) tuples."""
        ops = []
        tokens = cmd_str.split('|')
        for token in tokens:
            token = token.strip()
            if not token:
                continue
            ops.append(cls._parse_operator_token(token))
        return ops

    @classmethod
    def execute_chain(
        cls,
        image: Image.Image,
        cmd_str: str,
        extra_config: Dict[str, Any] | None = None,
    ) -> List[Image.Image]:
        if not ProcessorRegistry.list_all():
            from image_splitter.core import register_all_processors
            register_all_processors()

        ops = cls.parse_command(cmd_str)
        current_images = [image]
        extra = extra_config or {}
        
        try:
            for op_name, props in ops:
                processor = ProcessorRegistry.get(op_name)
                
                props_with_extra = {**extra, **props}
                coerced_props = coerce_processor_config(processor, props_with_extra)
                
                next_step_images = []
                for img in current_images:
                    try:
                        results = processor.process(img, coerced_props)
                        for res_img, _ in results:
                            next_step_images.append(res_img)
                    finally:
                        if img != image:
                            img.close()
                
                current_images = next_step_images
            return current_images
        except Exception:
            for img in current_images:
                if img != image:
                    try:
                        img.close()
                    except Exception:
                        pass
            raise
