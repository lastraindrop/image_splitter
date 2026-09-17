# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for a single-file Image Splitter Pro GUI build.

Usage (from the repository root):

    pip install pyinstaller pillow customtkinter
    pyinstaller packaging/image_splitter.spec

Output: dist/ImageSplitterPro.exe (Windows) / ImageSplitterPro (POSIX).

customtkinter ships non-Python asset files (theme JSON), hence
``--collect-all customtkinter``; Pillow is collected automatically via
imports but its plugins need no special handling for PNG/JPEG/WebP/BMP.
"""
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = collect_all("customtkinter")

a = Analysis(
    ["../image_splitter/gui.py"],
    pathex=[".."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports + [
        "image_splitter",
        "image_splitter.gui",
        "image_splitter.cli",
        "image_splitter.core",
        "image_splitter.script_engine",
        "image_splitter.logging_config",
        "image_splitter.settings",
        "image_splitter.keymap",
        "image_splitter.models",
        # Every processor module must be importable in the frozen app —
        # register_all_processors() discovers them via pkgutil.
        "image_splitter.processors",
        "image_splitter.processors.splitter",
        "image_splitter.processors.custom_splitter",
        "image_splitter.processors.resizer",
        "image_splitter.processors.adjuster",
        "image_splitter.processors.format_converter",
        "image_splitter.processors.geometry",
        "image_splitter.processors.filters",
        "image_splitter.processors.color_adjuster",
        "image_splitter.processors.metadata",
        "image_splitter.processors.watermark",
        "image_splitter.processors.rounded_corner",
        "image_splitter.processors.border",
        "image_splitter.processors.smart_crop",
        "image_splitter.plugins.example_plugin",
        "PIL",
        "PIL._tkinter_finder",
    ],
    excludes=["pytest", "mypy", "setuptools", "pip"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="ImageSplitterPro",
    debug=False,
    strip=False,
    upx=False,
    console=False,          # GUI app — no console window
    disable_windowed_traceback=False,
)
