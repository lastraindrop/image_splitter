"""Utility for coercing configuration types from raw input."""
import ast
from typing import Any, Dict, List


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Cannot parse bool: {value}")


def _coerce_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        parsed = ast.literal_eval(value)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, tuple):
            return list(parsed)
    raise ValueError(f"Cannot parse list: {value}")


def _coerce_value(meta: Dict[str, Any], value: Any) -> Any:
    value_type = meta.get("type", "str")

    if value_type == "int":
        return int(value)
    if value_type == "float":
        return float(value)
    if value_type == "bool":
        return _coerce_bool(value)
    if value_type == "list":
        return _coerce_list(value)
    if value_type == "enum":
        normalized = str(value)
        options = meta.get("options") or []
        if options and normalized not in options:
            raise ValueError(f"Value '{normalized}' not in options: {options}")
        return normalized

    return str(value)


def coerce_processor_config(processor: Any, raw_config: Dict[str, Any]) -> Dict[str, Any]:
    metadata = processor.get_ui_metadata()
    coerced: Dict[str, Any] = {}

    for meta in metadata:
        name = meta["name"]
        raw_value = raw_config.get(name, meta.get("default"))
        try:
            coerced[name] = _coerce_value(meta, raw_value)
        except Exception as exc:
            label = meta.get("label", name)
            raise ValueError(f"Parameter '{label}' requires {meta.get('type', 'str')}") from exc

    for key, value in raw_config.items():
        if key not in coerced:
            coerced[key] = value

    return coerced
