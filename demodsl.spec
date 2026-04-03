# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for demodsl standalone binary."""

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
    strip=True,
    upx=True,
    console=True,
)
