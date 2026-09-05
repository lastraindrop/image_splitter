"""Command parsing and chained dispatching for operators."""
import ast

from typing import Any, Dict, List, Tuple

from PIL import Image

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
            value_node = keyword.value
            # Ergonomic DSL: accept bare identifiers as string values so
            # users can write `style=solid`, `format=WebP`, `anchor=TL`
            # without quoting.  Numbers, lists, and quoted strings still
            # flow through ast.literal_eval unchanged.  Note: hex colors
            # like `#ff0000` still require quoting because `#` starts a
            # Python comment — use color="#ff0000".
            if isinstance(value_node, ast.Name):
                props[keyword.arg] = value_node.id
                continue
            try:
                props[keyword.arg] = ast.literal_eval(value_node)
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
        """Execute a command string via the Node Graph engine.

        .. deprecated::
            Prefer :meth:`ChainAsGraph.execute_chain` for unified execution.
            This method now delegates to it internally.
        """
        from image_splitter.engine.legacy_adapter import ChainAsGraph
        return ChainAsGraph.execute_chain(image, cmd_str, extra_config)
