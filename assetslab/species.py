# =========================================================================
# AssetsLab — 物种模块
# =========================================================================
# 独立的领域模块：负责物种（3D 骨骼拓扑）及其 3D 动作（actions3d）的读写。
# 自包含：自己管理 species/<id>/ 目录下的文件，不依赖其他模块。
#
# 目录结构：
#   species/<id>/skeleton.json        — 3D 骨骼拓扑（含 preset_schema 自描述）
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
    """物种模块：管理 3D 骨骼拓扑与 3D 动作。"""

    def __init__(self, root: Path) -> None:
        self._root = root

    # -- 内部路径 --

    def _skeleton_path(self, species_id: str) -> Path:
        return self._root / species_id / "skeleton.json"

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
        """创建物种文件夹 + skeleton.json + actions/。"""
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
        return sp_id

    def update(self, species_id: str, data: SpeciesSkeleton) -> str:
        """更新 skeleton.json。"""
        sp_dir = self._root / species_id
        sp_dir.mkdir(parents=True, exist_ok=True)
        (sp_dir / "actions3d").mkdir(exist_ok=True)
        self._save_json(self._skeleton_path(species_id), data)
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
