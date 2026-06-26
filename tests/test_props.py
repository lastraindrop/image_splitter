"""Unit tests for the typed Property descriptor system (engine/props.py)."""

import pytest

from image_splitter.engine.props import (
    BoolProp,
    ColorProp,
    EnumProp,
    FloatProp,
    IntProp,
    ListProp,
    Property,
    StrProp,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _TestContainer:
    """Minimal class to host property descriptors for testing."""

    def __init__(self) -> None:
        self._prop_values: dict = {}


# ---------------------------------------------------------------------------
# Property descriptor basics
# ---------------------------------------------------------------------------

def test_property_get_default():
    """Property returns default when never set."""
    prop = Property[int](default=42, name="answer")

    c = _TestContainer()
    c.__class__.answer = prop
    prop.__set_name__(c.__class__, "answer")

    assert c.answer == 42


def test_property_set_and_get():
    """Property stores and retrieves values."""
    prop = Property[int](default=0, name="x")

    c = _TestContainer()
    c.__class__.x = prop
    prop.__set_name__(c.__class__, "x")

    c.x = 99
    assert c.x == 99


def test_property_same_value_no_update():
    """Setting the same value does not trigger update callback."""
    calls: list = []

    def update(inst, attr, old, new):
        calls.append((old, new))

    prop = Property[int](default=10, name="v", update=update)

    c = _TestContainer()
    c.__class__.v = prop
    prop.__set_name__(c.__class__, "v")

    c.v = 10  # same as default
    assert len(calls) == 0

    c.v = 20  # different
    assert len(calls) == 1
    assert calls[0] == (10, 20)


def test_property_update_callback_args():
    """Update callback receives (instance, attr_name, old_value, new_value)."""
    captured: list = []

    def update(inst, attr, old, new):
        captured.append((inst, attr, old, new))

    prop = Property[str](default="a", name="letter", update=update)

    c = _TestContainer()
    c.__class__.letter = prop
    prop.__set_name__(c.__class__, "letter")

    c.letter = "b"
    assert len(captured) == 1
    inst, attr, old, new = captured[0]
    assert inst is c
    assert attr == "letter"
    assert old == "a"
    assert new == "b"


# ---------------------------------------------------------------------------
# Coercion – IntProp
# ---------------------------------------------------------------------------

def test_intprop_defaults():
    """IntProp defaults to 0 with no bounds."""
    p = IntProp()
    assert p.default == 0
    assert p.min_val is None
    assert p.max_val is None


def test_intprop_coerce_from_float():
    """IntProp coerces float → int (truncation)."""
    p = IntProp()

    c = _TestContainer()
    c.__class__.v = p
    p.__set_name__(c.__class__, "v")

    c.v = 3.7
    assert c.v == 3


def test_intprop_coerce_from_str():
    """IntProp coerces numeric string → int."""
    p = IntProp()

    c = _TestContainer()
    c.__class__.v = p
    p.__set_name__(c.__class__, "v")

    c.v = "42"
    assert c.v == 42
    assert isinstance(c.v, int)


def test_intprop_min_val():
    """IntProp raises ValueError when value < min_val."""
    p = IntProp(min_val=0)

    c = _TestContainer()
    c.__class__.v = p
    p.__set_name__(c.__class__, "v")

    c.v = 10  # ok
    with pytest.raises(ValueError):
        c.v = -1


def test_intprop_max_val():
    """IntProp raises ValueError when value > max_val."""
    p = IntProp(max_val=100)

    c = _TestContainer()
    c.__class__.v = p
    p.__set_name__(c.__class__, "v")

    c.v = 50  # ok
    with pytest.raises(ValueError):
        c.v = 200


# ---------------------------------------------------------------------------
# Coercion – FloatProp
# ---------------------------------------------------------------------------

def test_floatprop_coerce_from_int():
    """FloatProp coerces int → float."""
    p = FloatProp()

    c = _TestContainer()
    c.__class__.v = p
    p.__set_name__(c.__class__, "v")

    c.v = 5
    assert c.v == 5.0
    assert isinstance(c.v, float)


def test_floatprop_coerce_from_str():
    """FloatProp coerces numeric string → float."""
    p = FloatProp()

    c = _TestContainer()
    c.__class__.v = p
    p.__set_name__(c.__class__, "v")

    c.v = "3.14"
    assert c.v == 3.14


def test_floatprop_bounds():
    """FloatProp respects min/max bounds."""
    p = FloatProp(default=0.5, min_val=0.0, max_val=1.0)

    c = _TestContainer()
    c.__class__.v = p
    p.__set_name__(c.__class__, "v")

    c.v = 0.3  # ok
    with pytest.raises(ValueError):
        c.v = -0.1
    with pytest.raises(ValueError):
        c.v = 1.5


# ---------------------------------------------------------------------------
# Coercion – BoolProp
# ---------------------------------------------------------------------------

def test_boolprop_true_strings():
    """BoolProp accepts 'true'/'1'/'yes'/'on' as True."""
    p = BoolProp()

    c = _TestContainer()
    c.__class__.v = p
    p.__set_name__(c.__class__, "v")

    for s in ("true", "True", "TRUE", "1", "yes", "on"):
        c.v = s
        assert c.v is True, f"Failed for {s!r}"


def test_boolprop_false_strings():
    """BoolProp accepts 'false'/'0'/'no'/'off' as False."""
    p = BoolProp()

    c = _TestContainer()
    c.__class__.v = p
    p.__set_name__(c.__class__, "v")

    for s in ("false", "False", "FALSE", "0", "no", "off"):
        c.v = s
        assert c.v is False, f"Failed for {s!r}"


def test_boolprop_invalid_string():
    """BoolProp raises ValueError for unrecognized strings."""
    p = BoolProp()

    c = _TestContainer()
    c.__class__.v = p
    p.__set_name__(c.__class__, "v")

    with pytest.raises(ValueError):
        c.v = "maybe"


# ---------------------------------------------------------------------------
# Coercion – EnumProp
# ---------------------------------------------------------------------------

def test_enumprop_valid_choice():
    """EnumProp accepts values in its options list."""
    p = EnumProp(options=["small", "medium", "large"], default="medium")

    c = _TestContainer()
    c.__class__.v = p
    p.__set_name__(c.__class__, "v")

    assert c.v == "medium"
    c.v = "large"
    assert c.v == "large"


def test_enumprop_invalid_choice():
    """EnumProp raises ValueError for values not in options."""
    p = EnumProp(options=["red", "green", "blue"])

    c = _TestContainer()
    c.__class__.v = p
    p.__set_name__(c.__class__, "v")

    with pytest.raises(ValueError):
        c.v = "yellow"


# ---------------------------------------------------------------------------
# Coercion – StrProp
# ---------------------------------------------------------------------------

def test_strprop_coerce():
    """StrProp coerces any value to string."""
    p = StrProp()

    c = _TestContainer()
    c.__class__.v = p
    p.__set_name__(c.__class__, "v")

    c.v = 123
    assert c.v == "123"
    assert isinstance(c.v, str)


# ---------------------------------------------------------------------------
# Coercion – ListProp
# ---------------------------------------------------------------------------

def test_listprop_default_empty():
    """ListProp defaults to empty list when no default is given."""
    p = ListProp()
    assert p.default == []


def test_listprop_from_tuple():
    """ListProp coerces tuple → list."""
    p = ListProp()

    c = _TestContainer()
    c.__class__.v = p
    p.__set_name__(c.__class__, "v")

    c.v = (1, 2, 3)
    assert c.v == [1, 2, 3]


def test_listprop_from_str():
    """ListProp coerces Python list string → list."""
    p = ListProp()

    c = _TestContainer()
    c.__class__.v = p
    p.__set_name__(c.__class__, "v")

    c.v = "[4, 5, 6]"
    assert c.v == [4, 5, 6]


# ---------------------------------------------------------------------------
# Coercion – ColorProp
# ---------------------------------------------------------------------------

def test_colorprop_default():
    """ColorProp defaults to white (255, 255, 255, 255)."""
    p = ColorProp()
    assert p.default == (255, 255, 255, 255)


def test_colorprop_from_list():
    """ColorProp coerces list → tuple."""
    p = ColorProp()

    c = _TestContainer()
    c.__class__.v = p
    p.__set_name__(c.__class__, "v")

    c.v = [128, 64, 32, 255]
    assert c.v == (128, 64, 32, 255)
    assert isinstance(c.v, tuple)


def test_colorprop_from_str():
    """ColorProp coerces tuple string → tuple."""
    p = ColorProp()

    c = _TestContainer()
    c.__class__.v = p
    p.__set_name__(c.__class__, "v")

    c.v = "(255, 0, 0, 255)"
    assert c.v == (255, 0, 0, 255)


# ---------------------------------------------------------------------------
# to_ui_metadata
# ---------------------------------------------------------------------------

def test_intprop_ui_metadata():
    """IntProp to_ui_metadata returns correct keys."""
    p = IntProp(name="width", label="Width", default=100, min_val=1, max_val=4096)
    p.__set_name__(type("Dummy", (), {}), "width")
    meta = p.to_ui_metadata()
    assert meta["name"] == "width"
    assert meta["label"] == "Width"
    assert meta["type"] == "int"
    assert meta["default"] == 100
    assert meta["min"] == 1
    assert meta["max"] == 4096


def test_boolprop_ui_metadata():
    """BoolProp has ui_type='checkbox'."""
    p = BoolProp(name="enabled")
    p.__set_name__(type("Dummy", (), {}), "enabled")
    meta = p.to_ui_metadata()
    assert meta["type"] == "bool"
    assert meta["ui_type"] == "checkbox"


def test_enumprop_ui_metadata():
    """EnumProp has ui_type='dropdown' and options list."""
    p = EnumProp(options=["a", "b", "c"], default="b", name="choice")
    p.__set_name__(type("Dummy", (), {}), "choice")
    meta = p.to_ui_metadata()
    assert meta["type"] == "enum"
    assert meta["ui_type"] == "dropdown"
    assert meta["options"] == ["a", "b", "c"]


def test_colorprop_ui_metadata():
    """ColorProp has ui_type='color'."""
    p = ColorProp(name="bg")
    p.__set_name__(type("Dummy", (), {}), "bg")
    meta = p.to_ui_metadata()
    assert meta["type"] == "color"
    assert meta["ui_type"] == "color"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_set_none_value():
    """Property can store None."""
    prop = Property[int](default=0, name="x")

    c = _TestContainer()
    c.__class__.x = prop
    prop.__set_name__(c.__class__, "x")

    c.x = None
    assert c.x is None


def test_class_access_returns_descriptor():
    """Accessing property on the class returns the Property instance itself."""
    prop = Property[int](default=0, name="x")

    class Foo:
        x = prop

    prop.__set_name__(Foo, "x")
    assert Foo.x is prop
