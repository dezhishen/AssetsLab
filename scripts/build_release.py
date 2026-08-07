#!/usr/bin/env python3
"""AssetsLab 跨平台二进制构建：server（嵌入 web）+ cli，基于 pyinstaller。

产物（dist/）：
    assetslab-server[.exe]   — HTTP server（嵌入 Vue 前端 web/dist + 物种数据 data/species）
    assetslab-cli[.exe]      — 命令行工具（嵌入物种数据）

前置：
    1) 前端已构建：cd assetslab/web && pnpm build   （生成 assetslab/web/dist）
    2) 已安装 pyinstaller：pip install pyinstaller

运行：
    python scripts/build_release.py

设计要点：
    - --add-data 用 os.pathsep 分隔（Windows ';' / POSIX ':'）→ 跨平台
    - --onefile：单文件二进制；运行时资源解压到 sys._MEIPASS
    - 嵌入 data/species（只读资产），运行时由 config.ensure_species_seeded()
      首次播种到用户可写目录（presets 持久化）
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB_DIST = ROOT / "assetslab" / "web" / "dist"
DATA_SPECIES = ROOT / "data" / "species"
SEP = ";" if os.name == "nt" else ":"
EXE = ".exe" if os.name == "nt" else ""

# 版本号：优先环境变量 ASSETSLAB_VERSION（CI 从 tag 提取），否则取仓库最近 tag/commit
VERSION = os.environ.get("ASSETSLAB_VERSION", "").strip()


def _version_suffix() -> str:
    if VERSION:
        return VERSION.lstrip("v")
    # 本地：尝试 git 最近 tag，否则短 commit
    try:
        tag = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            capture_output=True, text=True, cwd=ROOT,
        ).stdout.strip()
        if tag:
            return tag.lstrip("v")
    except Exception:
        pass
    return "dev"


def _build(name: str, entry: Path) -> None:
    """pyinstaller --onefile 打包单个入口（嵌入 web + 物种数据）。"""
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--onefile",
        "--name", name,
        "--add-data", f"{WEB_DIST}{SEP}web/dist",
        "--add-data", f"{DATA_SPECIES}{SEP}data/species",
        str(entry),
    ]
    print(f"\n=== 构建 {name} ===")
    print("  " + " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)


def main() -> None:
    if not WEB_DIST.is_dir() or not (WEB_DIST / "index.html").is_file():
        sys.exit(f"[x] 前端未构建：{WEB_DIST}\n    请先运行：cd assetslab/web && pnpm build")
    if not DATA_SPECIES.is_dir():
        sys.exit(f"[x] 物种数据不存在：{DATA_SPECIES}")

    ver = _version_suffix()
    print(f"AssetsLab 版本: {ver}")

    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)

    _build("assetslab-server", ROOT / "assetslab" / "server.py")
    _build("assetslab-cli", ROOT / "assetslab" / "cli.py")

    # 重命名为带版本号的产物（便于 release 区分）
    print("\n=== 产物 ===")
    for name in ("assetslab-server", "assetslab-cli"):
        src = dist / f"{name}{EXE}"
        if src.is_file():
            tagged = dist / f"{name}-{ver}{EXE}"
            shutil.move(str(src), str(tagged))
            print(f"  {tagged.name}  {tagged.stat().st_size / 1024 / 1024:.1f} MiB")


if __name__ == "__main__":
    main()
