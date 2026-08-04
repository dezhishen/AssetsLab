# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the webflow CLI binary (onedir).

Run:  pyinstaller packaging/webflow-cli.spec
Cross-platform: data paths are resolved relative to this spec, so no
: vs ; separator issues on Windows.
"""
from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent

datas = [
    (str(ROOT / "workflow" / "definitions"), "workflow/definitions"),
    (str(ROOT / "workflow" / "templates"), "workflow/templates"),
    (str(ROOT / "workflow" / "body"), "workflow/body"),
    (str(ROOT / "workflow" / "motions"), "workflow/motions"),
]

a = Analysis(
    [str(ROOT / "scripts" / "webflow_cli.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[str(ROOT / "packaging")],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="webflow-cli",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="webflow-cli",
)
