# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the webflow server binary (onedir).

Bundles the engine data plus a copy of the built frontend (workflow/web/dist),
so a packaged server can serve the UI even when the user has no local build
(the server falls back to sys._MEIPASS/workflow/web/dist at runtime).

Run:  pyinstaller packaging/webflow-server.spec
"""
from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent

datas = [
    (str(ROOT / "workflow" / "definitions"), "workflow/definitions"),
    (str(ROOT / "workflow" / "templates"), "workflow/templates"),
    (str(ROOT / "workflow" / "body"), "workflow/body"),
    (str(ROOT / "workflow" / "motions"), "workflow/motions"),
    (str(ROOT / "workflow" / "web" / "dist"), "workflow/web/dist"),
]

a = Analysis(
    [str(ROOT / "scripts" / "webflow_server.py")],
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
    name="webflow-server",
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
    name="webflow-server",
)
