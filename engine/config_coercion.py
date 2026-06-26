"""Utility for coercing configuration types from raw input."""
import ast
import math
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

    # Handle missing values: fall back to default or skip entirely
    if value is None:
        default = meta.get("default")
        if default is not None:
            value = default
        else:
            return value

    if value_type == "int":
        # Handle float-string inputs like "3.0" — truncate via float first.
        # Guard against inf/nan: float("inf") and float("nan") produce
        # non-finite values that int() cannot consume; raise a clear error.
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                fv = float(value)
                if not math.isfinite(fv):
                    raise ValueError(
                        f"Invalid integer value: {value!r} "
                        f"(infinity and NaN are not accepted)"
                    )
                return int(fv)
        fv = float(value)
        if not math.isfinite(fv):
            raise ValueError(
                f"Invalid integer value: {value!r} "
                f"(infinity and NaN are not accepted)"
            )
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

    # Unknown type — fail loudly so developers can spot misconfigured
    # metadata, rather than silently converting everything to string.
    if value_type != "str":
        raise ValueError(
            f"Unknown parameter type '{value_type}' for '{meta.get('name', '?')}'. "
            f"Supported types: int, float, bool, list, enum, str."
        )

    return str(value)


def coerce_processor_config(processor: Any, raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce raw configuration dict to match processor metadata types.

    Args:
        processor: A processor instance with get_ui_metadata method.
        raw_config: Raw configuration dictionary from CLI or GUI.

    Returns:
        Coerced configuration dictionary with correct types.
    """
    metadata = processor.get_ui_metadata()
    coerced: Dict[str, Any] = {}

    for meta in metadata:
        name = meta["name"]
        raw_value = raw_config.get(name, meta.get("default"))
        try:
            coerced[name] = _coerce_value(meta, raw_value)
        except Exception as exc:
            label = meta.get("label", name)
            raise ValueError(
                f"Parameter '{label}': {exc}"
            ) from exc

    for key, value in raw_config.items():
        if key not in coerced:
            coerced[key] = value

    return coerced
