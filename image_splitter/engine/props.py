"""Typed Property descriptor system inspired by Blender's bpy.props.

Provides validated, coercible descriptor-properties with UI metadata generation.
Each ``Property[T]`` instance lives on a class and manages per-instance storage
through the descriptor protocol (``__set_name__``, ``__get__``, ``__set__``).

Convenience factories:
    ``IntProp``, ``FloatProp``, ``BoolProp``, ``EnumProp``,
    ``StrProp``, ``ListProp``, ``ColorProp``
"""
from __future__ import annotations

import ast
from typing import Any, Callable, Generic, Sequence, TypeVar

T = TypeVar("T")

# ---------------------------------------------------------------------------
# Update callback type
# ---------------------------------------------------------------------------
# ``update(instance, attr_name, old_value, new_value) -> None``
UpdateCallback = Callable[[Any, str, Any, Any], None]


# ---------------------------------------------------------------------------
# Core descriptor
# ---------------------------------------------------------------------------
class Property(Generic[T]):
    """Validated descriptor that coerces, bounds-checks, and notifies.

    **Experimental API** — inspired by Blender's ``bpy.props`` system.
    Not yet integrated into the main processing pipeline.  Provided for
    forward-compatibility with a future Node Graph UI.

    Args:
        default: Default value returned when the attribute has not been set.
        name: Programmatic identifier (auto-filled by ``__set_name__``).
        label: Human-readable label for UI display.
        min_val: Inclusive lower bound (``None`` = unbounded).
        max_val: Inclusive upper bound (``None`` = unbounded).
        options: Allowed values (used by ``EnumProp``).
        ui_type: Hint string for UI renderer (e.g. ``"checkbox"``).
        update: Callback fired after the value changes.
    """

    # Per-instance storage key prefix — keeps the descriptor's own state
    # separate from instance dicts.
    _STORAGE_ATTR: str = "_prop_values"

    def __init__(
        self,
        default: T | None = None,
        *,
        name: str | None = None,
        label: str | None = None,
        min_val: T | None = None,
        max_val: T | None = None,
        options: Sequence[str] | None = None,
        ui_type: str | None = None,
        update: UpdateCallback | None = None,
    ) -> None:
        self.default: T | None = default
        self.attr_name: str = name or ""
        self.label: str = label or self.attr_name
        self.min_val: T | None = min_val
        self.max_val: T | None = max_val
        self.options: tuple[str, ...] | None = (
            tuple(options) if options is not None else None
        )
        self.ui_type: str | None = ui_type
        self.update: UpdateCallback | None = update

    # -- descriptor protocol ------------------------------------------------

    def __set_name__(self, owner: type, name: str) -> None:
        """Called automatically when the descriptor is assigned to a class attribute."""
        self.attr_name = name
        if not self.label or self.label == "":
            self.label = name

    def __get__(self, instance: Any, owner: type | None = None) -> Any:
        """Return the stored value for *instance*, or the descriptor itself on class access."""
        if instance is None:
            return self
        storage = getattr(instance, self._STORAGE_ATTR, {})
        return storage.get(self.attr_name, self.default)

    def __set__(self, instance: Any, value: Any) -> None:
        """Coerce → validate → store → notify.

        The ``update`` callback is invoked **only** when the new value differs
        from the previously stored value.
        """
        coerced = self._coerce(value)
        self._validate(coerced)

        storage = getattr(instance, self._STORAGE_ATTR, None)
        if storage is None:
            storage = {}
            setattr(instance, self._STORAGE_ATTR, storage)

        old = storage.get(self.attr_name, self.default)
        storage[self.attr_name] = coerced

        if old != coerced and self.update is not None:
            self.update(instance, self.attr_name, old, coerced)

    # -- coercion -----------------------------------------------------------

    def _coerce(self, value: Any) -> T:
        """Convert *value* to the expected Python type.

        Subclasses / factory functions override this for type-specific logic.
        The base implementation returns *value* unchanged.
        """
        return value  # type: ignore[no-any-return]

    # -- validation ---------------------------------------------------------

    def _validate(self, value: T) -> None:
        """Check bounds and options.  Raises ``ValueError`` on failure."""
        if self.options is not None and value not in self.options:
            raise ValueError(
                f"Value {value!r} not in allowed options: {list(self.options)}"
            )
        if self.min_val is not None and value < self.min_val:  # type: ignore[operator]
            raise ValueError(
                f"Value {value!r} below minimum {self.min_val!r}"
            )
        if self.max_val is not None and value > self.max_val:  # type: ignore[operator]
            raise ValueError(
                f"Value {value!r} above maximum {self.max_val!r}"
            )

    # -- UI metadata --------------------------------------------------------

    def to_ui_metadata(self) -> dict[str, Any]:
        """Return a dict compatible with the existing ``get_ui_metadata()`` format.

        Returns:
            Dictionary with keys ``name``, ``label``, ``type``, ``default``,
            plus optional ``min``, ``max``, ``options``, ``ui_type``.
        """
        meta: dict[str, Any] = {
            "name": self.attr_name,
            "label": self.label,
            "type": self._ui_type_name(),
            "default": self.default,
        }
        if self.min_val is not None:
            meta["min"] = self.min_val
        if self.max_val is not None:
            meta["max"] = self.max_val
        if self.options is not None:
            meta["options"] = list(self.options)
        if self.ui_type is not None:
            meta["ui_type"] = self.ui_type
        return meta

    def _ui_type_name(self) -> str:
        """Return the type string used in UI metadata (override in subclasses)."""
        return "str"


# ---------------------------------------------------------------------------
# Concrete property classes with coercion
# ---------------------------------------------------------------------------

class _IntProperty(Property[int]):
    """Integer property with optional min/max bounds."""

    def _coerce(self, value: Any) -> int:
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            return int(value.strip())
        return int(value)

    def _ui_type_name(self) -> str:
        return "int"


class _FloatProperty(Property[float]):
    """Floating-point property with optional min/max bounds."""

    def _coerce(self, value: Any) -> float:
        if isinstance(value, float):
            return value
        if isinstance(value, (int, bool)):
            return float(value)
        if isinstance(value, str):
            return float(value.strip())
        return float(value)

    def _ui_type_name(self) -> str:
        return "float"


class _BoolProperty(Property[bool]):
    """Boolean property with permissive string coercion."""

    def _coerce(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return bool(value)
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes", "on"}:
                return True
            if normalized in {"false", "0", "no", "off"}:
                return False
            raise ValueError(f"Cannot parse bool from string: {value!r}")
        return bool(value)

    def _ui_type_name(self) -> str:
        return "bool"


class _EnumProperty(Property[str]):
    """Enumeration property backed by a list of allowed string options."""

    def _coerce(self, value: Any) -> str:
        return str(value).strip()

    def _ui_type_name(self) -> str:
        return "enum"


class _StrProperty(Property[str]):
    """String property."""

    def _coerce(self, value: Any) -> str:
        return str(value)

    def _ui_type_name(self) -> str:
        return "str"


class _ListProperty(Property[list[Any]]):
    """List property coerced from strings via ``ast.literal_eval``."""

    def _coerce(self, value: Any) -> list[Any]:
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
            raise ValueError(f"String did not evaluate to a list: {value!r}")
        return list(value)

    def _ui_type_name(self) -> str:
        return "list"


class _ColorProperty(Property[tuple[Any, ...]]):
    """RGBA colour property stored as a tuple of ints ``(R, G, B, A)``."""

    def _coerce(self, value: Any) -> tuple[Any, ...]:
        if isinstance(value, tuple):
            return value
        if isinstance(value, list):
            return tuple(value)
        if isinstance(value, str):
            parsed = ast.literal_eval(value)
            if isinstance(parsed, (list, tuple)):
                return tuple(parsed)
            raise ValueError(f"Cannot parse color from string: {value!r}")
        return tuple(value)

    def _ui_type_name(self) -> str:
        return "color"


# ---------------------------------------------------------------------------
# Public factory functions
# ---------------------------------------------------------------------------

def IntProp(
    default: int = 0,
    *,
    name: str | None = None,
    label: str | None = None,
    min_val: int | None = None,
    max_val: int | None = None,
    update: UpdateCallback | None = None,
) -> _IntProperty:
    """Create an integer property descriptor.

    Args:
        default: Default integer value.
        name: Programmatic name (auto-filled by ``__set_name__``).
        label: Human-readable label for UI.
        min_val: Inclusive lower bound.
        max_val: Inclusive upper bound.
        update: Callback ``f(instance, attr, old, new)``.

    Returns:
        Configured ``_IntProperty`` descriptor.
    """
    return _IntProperty(
        default=default,
        name=name,
        label=label,
        min_val=min_val,
        max_val=max_val,
        update=update,
    )


def FloatProp(
    default: float = 0.0,
    *,
    name: str | None = None,
    label: str | None = None,
    min_val: float | None = None,
    max_val: float | None = None,
    update: UpdateCallback | None = None,
) -> _FloatProperty:
    """Create a floating-point property descriptor.

    Args:
        default: Default float value.
        name: Programmatic name (auto-filled by ``__set_name__``).
        label: Human-readable label for UI.
        min_val: Inclusive lower bound.
        max_val: Inclusive upper bound.
        update: Callback ``f(instance, attr, old, new)``.

    Returns:
        Configured ``_FloatProperty`` descriptor.
    """
    return _FloatProperty(
        default=default,
        name=name,
        label=label,
        min_val=min_val,
        max_val=max_val,
        update=update,
    )


def BoolProp(
    default: bool = False,
    *,
    name: str | None = None,
    label: str | None = None,
    update: UpdateCallback | None = None,
) -> _BoolProperty:
    """Create a boolean property descriptor with UI type ``checkbox``.

    Coercion accepts ``"true"/"1"/"yes"/"on"`` → ``True`` and
    ``"false"/"0"/"no"/"off"`` → ``False``.

    Args:
        default: Default boolean value.
        name: Programmatic name (auto-filled by ``__set_name__``).
        label: Human-readable label for UI.
        update: Callback ``f(instance, attr, old, new)``.

    Returns:
        Configured ``_BoolProperty`` descriptor.
    """
    return _BoolProperty(
        default=default,
        name=name,
        label=label,
        ui_type="checkbox",
        update=update,
    )


def EnumProp(
    options: Sequence[str],
    default: str = "",
    *,
    name: str | None = None,
    label: str | None = None,
    update: UpdateCallback | None = None,
) -> _EnumProperty:
    """Create an enumeration property descriptor with UI type ``dropdown``.

    Args:
        options: Sequence of allowed string values.
        default: Default option (must appear in *options* or be empty).
        name: Programmatic name (auto-filled by ``__set_name__``).
        label: Human-readable label for UI.
        update: Callback ``f(instance, attr, old, new)``.

    Returns:
        Configured ``_EnumProperty`` descriptor.
    """
    return _EnumProperty(
        default=default,
        name=name,
        label=label,
        options=options,
        ui_type="dropdown",
        update=update,
    )


def StrProp(
    default: str = "",
    *,
    name: str | None = None,
    label: str | None = None,
    update: UpdateCallback | None = None,
) -> _StrProperty:
    """Create a string property descriptor.

    Args:
        default: Default string value.
        name: Programmatic name (auto-filled by ``__set_name__``).
        label: Human-readable label for UI.
        update: Callback ``f(instance, attr, old, new)``.

    Returns:
        Configured ``_StrProperty`` descriptor.
    """
    return _StrProperty(
        default=default,
        name=name,
        label=label,
        update=update,
    )


def ListProp(
    default: list[Any] | None = None,
    *,
    name: str | None = None,
    label: str | None = None,
    update: UpdateCallback | None = None,
) -> _ListProperty:
    """Create a list property descriptor.

    String values are coerced via ``ast.literal_eval``.

    Args:
        default: Default list value.
        name: Programmatic name (auto-filled by ``__set_name__``).
        label: Human-readable label for UI.
        update: Callback ``f(instance, attr, old, new)``.

    Returns:
        Configured ``_ListProperty`` descriptor.
    """
    return _ListProperty(
        default=default if default is not None else [],
        name=name,
        label=label,
        update=update,
    )


def ColorProp(
    default: tuple[int, ...] = (255, 255, 255, 255),
    *,
    name: str | None = None,
    label: str | None = None,
    update: UpdateCallback | None = None,
) -> _ColorProperty:
    """Create an RGBA color property descriptor with UI type ``color``.

    Args:
        default: Default colour as ``(R, G, B, A)`` tuple.
        name: Programmatic name (auto-filled by ``__set_name__``).
        label: Human-readable label for UI.
        update: Callback ``f(instance, attr, old, new)``.

    Returns:
        Configured ``_ColorProperty`` descriptor.
    """
    return _ColorProperty(
        default=default,
        name=name,
        label=label,
        ui_type="color",
        update=update,
    )
