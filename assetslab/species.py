# =========================================================================
# AssetsLab — 物种模块
# =========================================================================
# 独立的领域模块：负责物种（3D 骨骼拓扑）及其 3D 动作（actions3d）的读写。
# 自包含：自己管理 species/<id>/ 目录下的文件，不依赖其他模块。
#
# 目录结构：
#   species/<id>/skeleton.json        — 3D 骨骼拓扑（纯骨架，无预设信息）
#   species/<id>/preset_schema.json   — 预设 schema（随骨架自动派生：创建预设只需按此清单填充）
#   species/<id>/actions3d/<id>.json  — 3D 动作定义
# =========================================================================

from __future__ import annotations

import json
import shutil
from pathlib import Path

from .models import (
    ActionSummary,
    BoneMap,
    Motion,
    SpeciesDetail,
    SpeciesListItem,
    SpeciesSkeleton,
)


class SpeciesService:
    """物种模块：管理 3D 骨骼拓扑、预设 schema 与 3D 动作。"""

    def __init__(self, root: Path) -> None:
        self._root = root

    # -- 内部路径 --

    def _skeleton_path(self, species_id: str) -> Path:
        return self._root / species_id / "skeleton.json"

    def _preset_schema_path(self, species_id: str) -> Path:
        return self._root / species_id / "preset_schema.json"

    def _actions_dir(self, species_id: str) -> Path:
        return self._root / species_id / "actions3d"

    def _action_path(self, species_id: str, action_id: str) -> Path:
        return self._actions_dir(species_id) / f"{action_id}.json"

    @staticmethod
    def _load_json(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _save_json(path: Path, data: dict) -> None:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # -- 预设 schema（派生，随物种自动生成/更新） --

    @staticmethod
    def build_preset_schema(skel: dict, existing_params: dict | None = None) -> dict:
        """从骨架拓扑派生预设 schema（数据驱动，不硬编码关节/参数名）。

        - joints_3d 从 bones_3d 收集
        - views_2d 从 bones(front/side/back) 收集
        - params 从 param_chains 派生（保留 existing_params 中人工定义的 label/min/max 等）
        """
        def _collect(bones):
            out, seen = [], set()
            for a, b in bones:
                for j in (a, b):
                    if j not in seen:
                        seen.add(j)
                        out.append(j)
            return out

        joints_3d = _collect(skel.get("bones_3d", []))
        views_2d = {v: _collect(skel.get("bones", {}).get(v, [])) for v in ("front", "side", "back")}
        old = existing_params or {}
        params: dict = {}
        for chain in skel.get("param_chains", {}).values():
            pname = chain.get("param")
            if not pname or pname in params:
                continue
            base = {"default": 1.0, "min": 0.6, "max": 1.6, "step": 0.05, "label": pname}
            base.update(old.get(pname, {}))
            params[pname] = base
        return {
            "schema": "assetslab_preset_schema_v1",
            "species": skel.get("species_id"),
            "description": "预设 schema（随物种骨架自动派生）：创建预设只需按此清单填充（positions_3d 为主；positions 2D 可由 3D 投影派生）。",
            "required_fields": [
                "preset_id", "schema", "title", "description", "species",
                "positions_3d", "positions", "params", "body", "canvas", "head_radius",
            ],
            "joints_3d": joints_3d,
            "views_2d": views_2d,
            "params": params,
            "canvas": {"width": 960, "height": 600, "floor_y": 470},
            "head_radius": 24,
            "body_default": {k: 1.0 for k in params},
        }

    def _write_preset_schema(self, species_id: str, skel: dict) -> None:
        """派生并写 species/<id>/preset_schema.json（保留已有 params 的人工数值定义）。"""
        path = self._preset_schema_path(species_id)
        old: dict = {}
        if path.is_file():
            try:
                old = json.loads(path.read_text(encoding="utf-8")).get("params", {})
            except Exception:
                old = {}
        self._save_json(path, self.build_preset_schema(skel, old))

    def get_preset_schema(self, species_id: str) -> dict | None:
        """读取 species/<id>/preset_schema.json（不存在返回 None）。"""
        path = self._preset_schema_path(species_id)
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    # -- 物种 CRUD --

    def list(self) -> list[SpeciesListItem]:
        """列出所有物种（自动发现 actions/ 目录）。"""
        items: list[SpeciesListItem] = []
        if not self._root.is_dir():
            return items
        for sp_dir in sorted(self._root.iterdir()):
            if not sp_dir.is_dir():
                continue
            skel = sp_dir / "skeleton.json"
            if not skel.is_file():
                continue
            try:
                d: SpeciesSkeleton = json.loads(skel.read_text(encoding="utf-8"))
            except Exception:
                continue
            sp_id = d.get("species_id", sp_dir.name)
            bones: BoneMap = d.get("bones", {})
            total_bones = sum(len(v) for v in bones.values())
            actions = self.list_actions(sp_id)
            items.append({
                "id": sp_id,
                "title": d.get("title", sp_id),
                "description": d.get("description", ""),
                "joint_count": sum(len(v) for k, v in d.get("joints", {}).items() if k != "aliases"),
                "bone_count": total_bones,
                "chain_count": len(d.get("chains", {})),
                "param_chain_count": len(d.get("param_chains", {})),
                "motions": [a["id"] for a in actions],
                "actions": actions,
            })
        return items

    def get(self, species_id: str) -> SpeciesDetail:
        """获取物种详情（skeleton + 全部动作）。"""
        skel_path = self._skeleton_path(species_id)
        if not skel_path.is_file():
            raise KeyError(f"species not found: {species_id}")
        data: SpeciesDetail = json.loads(skel_path.read_text(encoding="utf-8"))
        data["actions"] = []
        actions_dir = self._actions_dir(species_id)
        if actions_dir.is_dir():
            for af in sorted(actions_dir.glob("*.json")):
                if af.name == "base.json":
                    continue
                try:
                    data["actions"].append(json.loads(af.read_text(encoding="utf-8")))
                except Exception:
                    pass
        return data

    def create(self, data: SpeciesSkeleton) -> str:
        """创建物种文件夹 + skeleton.json + preset_schema.json + actions3d/。"""
        sp_id = data.get("species_id", "").strip()
        if not sp_id:
            raise ValueError("species_id required")
        sp_dir = self._root / sp_id
        if sp_dir.exists():
            raise FileExistsError(f"species already exists: {sp_id}")
        sp_dir.mkdir(parents=True, exist_ok=True)
        (sp_dir / "actions3d").mkdir(exist_ok=True)
        data.setdefault("schema", "assetslab_species_v1")
        self._save_json(self._skeleton_path(sp_id), data)
        self._write_preset_schema(sp_id, data)
        return sp_id

    def update(self, species_id: str, data: SpeciesSkeleton) -> str:
        """更新 skeleton.json，并同步重派生 preset_schema.json。"""
        sp_dir = self._root / species_id
        sp_dir.mkdir(parents=True, exist_ok=True)
        (sp_dir / "actions3d").mkdir(exist_ok=True)
        self._save_json(self._skeleton_path(species_id), data)
        self._write_preset_schema(species_id, data)
        return species_id

    def delete(self, species_id: str) -> str:
        """删除整个物种文件夹。"""
        sp_dir = self._root / species_id
        if not sp_dir.is_dir():
            raise KeyError(f"species not found: {species_id}")
        shutil.rmtree(sp_dir)
        return species_id

    # -- 动作管理（属于物种） --

    def list_actions(self, species_id: str) -> list[ActionSummary]:
        """列出某物种的全部动作摘要。"""
        actions: list[ActionSummary] = []
        actions_dir = self._actions_dir(species_id)
        if not actions_dir.is_dir():
            return actions
        for af in sorted(actions_dir.glob("*.json")):
            try:
                ad = json.loads(af.read_text(encoding="utf-8"))
                actions.append({
                    "id": ad.get("motion_id", af.stem),
                    "title": ad.get("title", af.stem),
                    "params": ad.get("params", {}),
                })
            except Exception:
                actions.append({"id": af.stem, "title": af.stem, "params": {}})
        return actions

    def get_action(self, species_id: str, action_id: str) -> Motion:
        """获取某物种的单个动作定义。"""
        path = self._action_path(species_id, action_id)
        if not path.is_file():
            raise KeyError(f"action not found: {species_id}/{action_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def save_action(self, species_id: str, action_id: str, data: Motion) -> str:
        """保存动作到 species/<id>/actions3d/<action_id>.json。"""
        self._actions_dir(species_id).mkdir(parents=True, exist_ok=True)
        self._save_json(self._action_path(species_id, action_id), data)
        return action_id

    def delete_action(self, species_id: str, action_id: str) -> str:
        """删除动作文件。"""
        path = self._action_path(species_id, action_id)
        if not path.is_file():
            raise KeyError(f"action not found: {species_id}/{action_id}")
        path.unlink()
        return action_id

    def find_action(self, action_id: str) -> tuple[str, Motion] | None:
        """跨物种查找动作。返回 (species_id, motion)。找不到返回 None。"""
        if not self._root.is_dir():
            return None
        for sp_dir in sorted(self._root.iterdir()):
            if not sp_dir.is_dir():
                continue
            p = sp_dir / "actions3d" / f"{action_id}.json"
            if p.is_file():
                return sp_dir.name, json.loads(p.read_text(encoding="utf-8"))
        return None

    def list_actions_all(self) -> list[dict]:
        """跨物种列出全部 3D 动作（含所属物种信息）。"""
        items: list[dict] = []
        if not self._root.is_dir():
            return items
        for sp_dir in sorted(self._root.iterdir()):
            if not sp_dir.is_dir():
                continue
            species_id = sp_dir.name
            actions_dir = sp_dir / "actions3d"
            if not actions_dir.is_dir():
                continue
            for af in sorted(actions_dir.glob("*.json")):
                try:
                    d: Motion = json.loads(af.read_text(encoding="utf-8"))
                except Exception:
                    continue
                items.append({
                    "id": d.get("motion_id", af.stem),
                    "title": d.get("title", d.get("motion_id", af.stem)),
                    "description": d.get("description", ""),
                    "species": species_id,
                    "params": d.get("params", {}),
                    "has_ik": bool(d.get("ik3d")),
                })
        return items
