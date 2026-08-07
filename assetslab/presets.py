# =========================================================================
# AssetsLab — 预设模块（Preset）
# =========================================================================
# 预设 = 基于物种的具体实例：一套体型参数（body，调整骨骼尺寸）+ 各动作参数
# （actions，调整动作幅度）。物种提供 schema（体型参数 schema + 动作参数 schema），
# 预设只需提供参数值，界面按 schema 渲染参数面板。
#
# 目录结构：
#   presets/<preset_id>.json   — 预设定义（值），schema 由物种派生
# =========================================================================

from __future__ import annotations

import json
from pathlib import Path

from .models import Preset, PresetSummary
from .species import SpeciesService

PRESET_SCHEMA = "assetslab_preset_v1"


class PresetService:
    """预设模块：管理 presets/<id>.json，派生完整 schema（物种体型 + 动作参数）。"""

    def __init__(self, root: Path, species: SpeciesService) -> None:
        self._root = root
        self._species = species

    # -- 内部路径 --

    def _path(self, preset_id: str) -> Path:
        return self._root / f"{preset_id}.json"

    @staticmethod
    def _load(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _save(path: Path, data: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # -- schema（数据驱动：物种体型参数 + 各动作参数） --

    def build_preset_schema(self, species_id: str) -> dict:
        """派生预设完整 schema（供前端参数面板渲染）。

        - body_params: 体型参数（物种 preset_schema.json，随骨架 param_chains 派生）
        - actions: 各动作的 params（从动作 JSON 读取，调整动作幅度）
        - default_body: 物种默认体型（default.json body）
        """
        ps = self._species.get_preset_schema(species_id) or {}
        body_params: dict = ps.get("params", {})
        default_body: dict = {}
        try:
            default_body = (self._species.get_default(species_id) or {}).get("body", {})
        except Exception:
            default_body = {k: 1.0 for k in body_params}
        actions: dict = {}
        for act in self._species.list_actions(species_id):
            actions[act["id"]] = {"title": act.get("title", act["id"]), "params": act.get("params", {})}
        return {
            "species": species_id,
            "body_params": body_params,
            "default_body": default_body,
            "actions": actions,
        }

    # -- CRUD --

    def list(self) -> list[PresetSummary]:
        items: list[PresetSummary] = []
        if not self._root.is_dir():
            return items
        for pf in sorted(self._root.glob("*.json")):
            try:
                d = json.loads(pf.read_text(encoding="utf-8"))
                items.append({
                    "preset_id": d.get("preset_id", pf.stem),
                    "title": d.get("title", pf.stem),
                    "description": d.get("description", ""),
                    "species": d.get("species", ""),
                })
            except Exception:
                continue
        return items

    def get(self, preset_id: str) -> dict:
        """预设详情 = 预设值 + 完整 schema（species 体型 + 动作参数）。"""
        path = self._path(preset_id)
        if not path.is_file():
            raise KeyError(f"preset not found: {preset_id}")
        preset = json.loads(path.read_text(encoding="utf-8"))
        schema = self.build_preset_schema(preset.get("species", ""))
        return {**preset, "schema_info": schema}

    def new_schema(self, species_id: str) -> dict:
        """新建预设的空白表单：值 = 物种默认 + 完整 schema。"""
        schema = self.build_preset_schema(species_id)
        return {
            "schema": PRESET_SCHEMA,
            "preset_id": "",
            "species": species_id,
            "title": "",
            "description": "",
            "body": dict(schema["default_body"]),
            "actions": {aid: {} for aid in schema["actions"]},
            "schema_info": schema,
        }

    def create(self, data: Preset) -> str:
        pid = (data.get("preset_id") or "").strip()
        if not pid:
            raise ValueError("preset_id required")
        if not data.get("species"):
            raise ValueError("species required")
        if self._path(pid).exists():
            raise FileExistsError(f"preset already exists: {pid}")
        data = dict(data)
        data.pop("schema_info", None)  # schema 由物种派生，不持久化
        data.setdefault("schema", PRESET_SCHEMA)
        self._save(self._path(pid), data)
        return pid

    def update(self, preset_id: str, data: Preset) -> str:
        path = self._path(preset_id)
        if not path.is_file():
            raise KeyError(f"preset not found: {preset_id}")
        data = dict(data)
        data.pop("schema_info", None)  # schema 由物种派生，不持久化
        data.setdefault("schema", PRESET_SCHEMA)
        data["preset_id"] = data.get("preset_id") or preset_id
        self._save(path, data)
        return data["preset_id"]

    def delete(self, preset_id: str) -> str:
        path = self._path(preset_id)
        if not path.is_file():
            raise KeyError(f"preset not found: {preset_id}")
        path.unlink()
        return preset_id
