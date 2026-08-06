# =========================================================================
# AssetsLab — 模块接口契约（依赖倒置）
# =========================================================================
# 定义各领域模块对外暴露的能力（Protocol）。
# 模块之间只依赖这里声明的接口，不依赖具体实现。
#
# 领域模块（彼此几乎独立，仅存在真实领域关系）：
#   species.py  物种模块     — 自包含，无依赖
#   preset.py   预设模块     — 依赖物种模块接口（创建预设要读物种）
#   motion.py   动作模块     — 依赖物种模块接口（动作属于物种）
#   render.py   渲染模块     — 依赖预设+动作
#   server.py   组装所有模块
# =========================================================================

from __future__ import annotations

from typing import Protocol

from PIL import Image

from .models import (
    Motion,
    MotionListItem,
    Preset,
    PresetDetail,
    PresetListItem,
    SpeciesDetail,
    SpeciesListItem,
    SpeciesSkeleton,
    View,
)

# -------------------------------------------------------------------------
# 物种模块接口
# -------------------------------------------------------------------------


class SpeciesModule(Protocol):
    """物种模块对外能力：骨骼拓扑 + 动作管理。"""

    # -- 物种 CRUD --
    def list(self) -> list[SpeciesListItem]: ...
    def get(self, species_id: str) -> SpeciesDetail: ...
    def create(self, data: SpeciesSkeleton) -> str: ...
    def update(self, species_id: str, data: SpeciesSkeleton) -> str: ...
    def delete(self, species_id: str) -> str: ...

    # -- 动作管理（属于物种） --
    def list_actions(self, species_id: str) -> list[dict]: ...
    def get_action(self, species_id: str, action_id: str) -> Motion: ...
    def save_action(self, species_id: str, action_id: str, data: Motion) -> str: ...
    def delete_action(self, species_id: str, action_id: str) -> str: ...
    def find_action(self, action_id: str) -> tuple[str, Motion] | None: ...


# -------------------------------------------------------------------------
# 预设模块接口
# -------------------------------------------------------------------------


class PresetModule(Protocol):
    """预设模块对外能力。"""

    def list(self) -> list[PresetListItem]: ...
    def get(self, preset_id: str) -> PresetDetail: ...
    def save(self, preset_id: str, data: Preset) -> str: ...


# -------------------------------------------------------------------------
# 渲染模块接口
# -------------------------------------------------------------------------


class RenderService(Protocol):
    """渲染模块对外能力：骨架预览 + 动作帧。返回 PIL Image。"""

    def skeleton_preview(self, skeleton_id: str, view: View) -> Image.Image:
        """渲染单个骨架姿势帧。skeleton_id 通常是预设 ID（含坐标）。"""
        ...

    def motion_frame(
        self,
        motion_id: str,
        *,
        view: View = "front",
        stage: str = "legs",
        skeleton: str = "standard",
        frame_index: int = 0,
        overrides: dict[str, float] | None = None,
        proportions: dict[str, float] | None = None,
    ) -> Image.Image:
        """渲染动作的一帧。"""
        ...
