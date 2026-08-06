# =========================================================================
# AssetsLab — 预设模块
# =========================================================================
# 领域模块：负责体型预设的读写。
# 依赖：创建/读取预设时，需要读取所属物种的骨骼拓扑（依赖 species 模块接口）。
# 目录结构：
#   presets/<id>.json — 体型预设（引用物种）
# =========================================================================

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from .models import Preset, PresetDetail, PresetListItem


class SpeciesReader(Protocol):
    """预设模块依赖的物种接口（只读部分）。

    预设只需要读取物种的骨骼拓扑来合并，不需要管理物种。
    定义成 Protocol，使预设模块只依赖"能读物种"这个能力，不依赖具体实现。
    """

    def get(self, species_id: str) -> dict:
        """返回物种详情（含 joints/bones/chains/param_chains）。"""
        ...


class PresetService:
    """预设模块：管理体型预设。

    通过 `species`（实现了 SpeciesReader 接口的对象）读取物种骨骼拓扑。
    """

    def __init__(self, presets_root: Path, species: SpeciesReader) -> None:
        """依赖注入物种模块（只使用其只读接口）。"""
        self._root = presets_root
        self._species = species

    def _preset_path(self, preset_id: str) -> Path:
        return self._root / f"{preset_id}.json"

    def list(self) -> list[PresetListItem]:
        """列出所有预设。"""
        items: list[PresetListItem] = []
        if not self._root.is_dir():
            return items
        for fp in sorted(self._root.glob("*.json")):
            try:
                d: Preset = json.loads(fp.read_text(encoding="utf-8"))
            except Exception:
                continue
            sid = d.get("preset_id") or d.get("skeleton_id")
            if not sid:
                continue
            items.append({
                "id": sid,
                "title": d.get("title", sid),
                "description": d.get("description", ""),
                "species": d.get("species"),
                "is_species": False,
                "is_preset": True,
                "body": d.get("body", {}),
                "views": list(d.get("positions", d.get("views", {})).keys()),
                "motions": [],
            })
        return items

    def get(self, preset_id: str) -> PresetDetail:
        """获取预设详情，并从所属物种合并骨骼数据。"""
        path = self._preset_path(preset_id)
        if not path.is_file():
            raise KeyError(f"skeleton not found: {preset_id}")
        data: PresetDetail = json.loads(path.read_text(encoding="utf-8"))
        species_ref = data.get("species")
        if species_ref:
            # 通过物种模块接口读取骨骼拓扑
            species = self._species.get(species_ref)
            if species:
                for key in ("param_chains", "chains", "joints", "bones"):
                    if key in species and key not in data:
                        data[key] = species[key]
                if "params" not in data and "params" in species:
                    data["params"] = species["params"]
        return data

    def save(self, preset_id: str, data: Preset) -> str:
        """保存预设到 presets/<id>.json（存在则覆盖）。"""
        self._root.mkdir(parents=True, exist_ok=True)
        path = self._preset_path(preset_id)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return preset_id

    def create(self, data: Preset) -> str:
        """创建预设（不存在时）。"""
        preset_id = data.get("preset_id", "").strip()
        if not preset_id:
            raise ValueError("preset_id required")
        path = self._preset_path(preset_id)
        if path.exists():
            raise FileExistsError(f"preset already exists: {preset_id}")
        return self.save(preset_id, data)

    def delete(self, preset_id: str) -> str:
        """删除预设文件。"""
        path = self._preset_path(preset_id)
        if not path.is_file():
            raise KeyError(f"skeleton not found: {preset_id}")
        path.unlink()
        return preset_id
