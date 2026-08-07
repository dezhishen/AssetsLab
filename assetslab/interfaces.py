# =========================================================================
# AssetsLab — 模块接口契约（依赖倒置）
# =========================================================================
# 定义各领域模块对外暴露的能力（Protocol）。
# 模块之间只依赖这里声明的接口，不依赖具体实现。
#
# 领域模块（彼此几乎独立，仅存在真实领域关系）：
#   species.py  物种模块     — 自包含，无依赖（骨架/默认参数/动作/约束数据）
#   motion.py   3D 动作 DSL 求值器（通用表达式求值，无状态）
#   render.py   3D 绘制原语（画布/骨骼/关节/头部）
#   skeleton3d.py 3D 骨架/动作引擎（读数据渲染、IK、校验支撑）
#   server.py   组装所有模块（仅 3D 端点，基于物种默认参数）
# =========================================================================

from __future__ import annotations

from typing import Protocol

from .models import (
    Motion,
    MotionListItem,
    SpeciesDetail,
    SpeciesListItem,
    SpeciesSkeleton,
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
