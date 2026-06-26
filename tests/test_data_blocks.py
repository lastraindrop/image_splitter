"""Unit tests for ImageDataBlock (engine/data_blocks.py)."""

import pytest

from image_splitter.engine.data_blocks import ImageDataBlock
from .conftest import make_rgb_image


@pytest.fixture(autouse=True)
def _clean_registry():
    """Ensure the global name registry is empty before and after each test."""
    ImageDataBlock.clear_all()
    yield
    ImageDataBlock.clear_all()


# ---------------------------------------------------------------------------
# Creation & Registration
# ---------------------------------------------------------------------------

def test_create_block_registers_in_registry():
    """ImageDataBlock is auto-registered in the class-level name registry."""
    block = ImageDataBlock(name="test", image=make_rgb_image())
    assert ImageDataBlock.get_by_name("test") is block


def test_create_block_without_image():
    """ImageDataBlock can be created without an image (None)."""
    block = ImageDataBlock(name="empty")
    assert block.image is None
    assert not block.is_loaded
    assert block.size == (0, 0)


def test_duplicate_name_overwrites():
    """Creating a block with an existing name silently replaces the old entry."""
    b1 = ImageDataBlock(name="dup", image=make_rgb_image(color=(255, 0, 0)))
    b2 = ImageDataBlock(name="dup", image=make_rgb_image(color=(0, 255, 0)))

    # Registry now points to the new block
    assert ImageDataBlock.get_by_name("dup") is b2
    # Old block's image was released to prevent memory leak
    assert not b1.is_loaded
    # New block holds its image
    assert b2.is_loaded
    assert b2.image is not None


# ---------------------------------------------------------------------------
# Version tracking
# ---------------------------------------------------------------------------

def test_version_starts_at_zero():
    """New blocks start at version 0."""
    block = ImageDataBlock(name="ver", image=make_rgb_image())
    assert block.version == 0


def test_version_increments_on_image_set():
    """Setting the image property increments the version."""
    block = ImageDataBlock(name="ver", image=make_rgb_image())
    v0 = block.version
    block.image = make_rgb_image(color=(0, 255, 0))
    assert block.version == v0 + 1


def test_version_unchanged_on_read():
    """Reading version (without mutation) does not change it."""
    block = ImageDataBlock(name="ver", image=make_rgb_image())
    v = block.version
    assert block.version == v
    assert block.version == v


def test_touch_increments_version():
    """touch() bumps the version counter without changing the image."""
    block = ImageDataBlock(name="ver", image=make_rgb_image())
    v0 = block.version
    block.touch()
    assert block.version == v0 + 1
    assert block.is_loaded  # image still present


# ---------------------------------------------------------------------------
# Reference counting
# ---------------------------------------------------------------------------

def test_use_increments_users():
    """use() increments the user count."""
    block = ImageDataBlock(name="ref", image=make_rgb_image())
    assert block.users == 0
    block.use()
    assert block.users == 1
    block.use()
    assert block.users == 2


def test_unuse_decrements_users():
    """unuse() decrements, clamped at 0."""
    block = ImageDataBlock(name="ref", image=make_rgb_image())
    block.use()
    block.use()
    block.unuse()
    assert block.users == 1
    block.unuse()
    assert block.users == 0


def test_unuse_at_zero_releases_image():
    """When users drops to 0, the image is released."""
    block = ImageDataBlock(name="ref", image=make_rgb_image())
    block.use()
    assert block.is_loaded
    block.unuse()  # drops to 0 → release
    assert not block.is_loaded


# ---------------------------------------------------------------------------
# Clone
# ---------------------------------------------------------------------------

def test_clone_creates_independent_copy():
    """clone() makes a new block with a copy of the image."""
    original = ImageDataBlock(name="orig", image=make_rgb_image(color=(255, 0, 0)))
    clone = original.clone("copy")

    assert clone.name == "copy"
    assert clone is not original
    assert clone.image is not None
    assert clone.image is not original.image  # different PIL image objects
    assert clone.image.size == original.image.size


def test_clone_has_fresh_version():
    """Cloned blocks start at version 0."""
    original = ImageDataBlock(name="orig", image=make_rgb_image())
    clone = original.clone("copy")
    assert clone.version == 0


def test_clone_registered_separately():
    """Cloned blocks are registered under the new name."""
    original = ImageDataBlock(name="orig", image=make_rgb_image())
    clone = original.clone("copy")
    assert ImageDataBlock.get_by_name("orig") is original
    assert ImageDataBlock.get_by_name("copy") is clone


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

def test_metadata_dpi_extraction():
    """DPI info from PIL image is extracted into metadata."""
    img = make_rgb_image()
    img.info["dpi"] = (72, 72)
    block = ImageDataBlock(name="meta", image=img)
    assert block.metadata.get("dpi") == (72, 72)


def test_metadata_icc_profile_extraction():
    """ICC profile from PIL image is extracted into metadata."""
    img = make_rgb_image()
    img.info["icc_profile"] = b"fake_icc"
    block = ImageDataBlock(name="meta", image=img)
    assert block.metadata.get("icc_profile") == b"fake_icc"


def test_metadata_dict_is_mutable():
    """The metadata dict can be modified directly."""
    block = ImageDataBlock(name="meta", image=make_rgb_image())
    block.metadata["custom"] = "hello"
    assert block.metadata["custom"] == "hello"


# ---------------------------------------------------------------------------
# Registry operations
# ---------------------------------------------------------------------------

def test_get_by_name_missing():
    """get_by_name returns None for unknown names."""
    assert ImageDataBlock.get_by_name("nonexistent") is None


def test_list_all():
    """list_all returns all registered blocks."""
    b1 = ImageDataBlock(name="a", image=make_rgb_image())
    b2 = ImageDataBlock(name="b", image=make_rgb_image())
    blocks = ImageDataBlock.list_all()
    assert len(blocks) == 2
    assert b1 in blocks
    assert b2 in blocks


def test_forget_releases_and_unregisters():
    """forget() releases the image and removes from registry."""
    block = ImageDataBlock(name="rm", image=make_rgb_image())
    ImageDataBlock.forget("rm")
    assert ImageDataBlock.get_by_name("rm") is None
    assert not block.is_loaded


def test_clear_all():
    """clear_all() releases all blocks and empties the registry."""
    ImageDataBlock(name="x", image=make_rgb_image())
    ImageDataBlock(name="y", image=make_rgb_image())
    ImageDataBlock.clear_all()
    assert len(ImageDataBlock.list_all()) == 0


# ---------------------------------------------------------------------------
# Size property
# ---------------------------------------------------------------------------

def test_size_returns_dimensions():
    """size property returns (width, height) of the image."""
    block = ImageDataBlock(name="s", image=make_rgb_image(size=(200, 150)))
    assert block.size == (200, 150)


def test_size_zero_when_no_image():
    """size returns (0, 0) when no image is loaded."""
    block = ImageDataBlock(name="empty")
    assert block.size == (0, 0)
