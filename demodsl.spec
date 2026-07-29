# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for demodsl standalone binary."""

import sys

# Stripping symbols corrupts the bundled DLLs on Windows: the executable
# builds, then dies at startup with
#   [PYI-ERROR] Failed to load Python DLL '...\\python312.dll'
# UPX has the same reputation on Windows, and it is not installed on the
# runners anyway, so both are limited to the platforms where they behave.
_WINDOWS = sys.platform == "win32"

a = Analysis(
    ["demodsl/cli.py"],
    pathex=[],
    binaries=[],
    datas=[("example.yaml", ".")],
    hiddenimports=[
        "demodsl.engine",
        "demodsl.models",
        "demodsl.config_loader",
        "demodsl.commands",
        "demodsl.stats",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="demodsl",
    debug=False,
    bootloader_ignore_signals=False,
    strip=not _WINDOWS,
    upx=not _WINDOWS,
    console=True,
)
