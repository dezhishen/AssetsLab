# =========================================================================
# AssetsLab — 全局配置
# =========================================================================
# 数据目录统一从这里定义：
#   - 默认数据目录为仓库根 data/（species 资产提交，presets 为运行时用户数据）
#   - server / CLI / 验证脚本均支持 --data-dir 覆盖（测试用 test-data/）
#   - pyinstaller 打包运行时：species 从 bundle（sys._MEIPASS）首次播种到
#     用户可写目录（presets 需持久化），见 ensure_species_seeded()
# =========================================================================

from __future__ import annotations

import shutil
import sys
from pathlib import Path


def _bundle_root() -> Path | None:
    """pyinstaller --onefile 打包运行时的资源根（sys._MEIPASS）；源码运行时 None。"""
    base = getattr(sys, "_MEIPASS", None)
    return Path(base) if base else None


REPO_ROOT = Path(__file__).resolve().parent.parent
BUNDLE_ROOT = _bundle_root()

if BUNDLE_ROOT is not None:
    # 打包运行时：默认数据目录为用户可写目录（物种只读、预设需持久化）
    DEFAULT_DATA_DIR = Path.home() / ".assetslab" / "data"
    BUNDLED_SPECIES = BUNDLE_ROOT / "data" / "species"
else:
    # 源码运行时：仓库根 data/（species 资产提交，presets 运行时用户数据）
    DEFAULT_DATA_DIR = REPO_ROOT / "data"
    BUNDLED_SPECIES = None


def ensure_species_seeded(data_dir: Path | None = None) -> Path:
    """确保物种数据可用。

    - 打包运行时首次运行：若数据目录无 species/，从 bundle 内播种（复制只读资源）。
    - 源码运行时：直接返回默认数据目录（data/species 已在仓库）。
    返回实际使用的数据目录。
    """
    data_dir = Path(data_dir) if data_dir is not None else DEFAULT_DATA_DIR
    if BUNDLED_SPECIES is not None and BUNDLED_SPECIES.is_dir():
        species_dir = data_dir / "species"
        if not species_dir.is_dir():
            species_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(BUNDLED_SPECIES, species_dir)
    return data_dir
