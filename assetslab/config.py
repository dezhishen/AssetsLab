# =========================================================================
# AssetsLab — 全局配置
# =========================================================================
# 数据目录统一从这里定义：
#   - 默认数据目录为仓库根 data/（species 资产提交，presets 为运行时用户数据）
#   - server / CLI / 验证脚本均支持 --data-dir 覆盖（测试用 test-data/）
# =========================================================================

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = REPO_ROOT / "data"
