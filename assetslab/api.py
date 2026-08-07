# =========================================================================
# AssetsLab — 统一 API 服务（CLI 与 HTTP 共享的同一套接口实现）
# =========================================================================
# 唯一的 API 实现：物种 + 动作 + 预设 + 3D 渲染。
# - HTTP（server.py）的 handler 只依赖这里的 ApiService（薄路由层，无业务逻辑）
# - CLI（python -m assetslab.cli）直接实例化 ApiService 交互，不启动 server
# - 硬约束：ApiService 必须满足 interfaces.Api（Protocol，@runtime_checkable），
#   任何新增操作先在 interfaces.Api 声明，两侧（CLI/HTTP）自动一致。
# =========================================================================

from __future__ import annotations

import base64
import io
from pathlib import Path

from .interfaces import Api
from .models import Motion, MotionListItem, Preset, PresetSummary, SpeciesDetail, SpeciesListItem, SpeciesSkeleton
from .presets import PresetService
from .species import SpeciesService


def image_to_data_url(img) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


class ApiService:
    """统一 API 实现：组合物种 + 预设服务，并承担 3D 渲染（CLI/HTTP 共用）。"""

    def __init__(self, species_root: Path, presets_root: Path) -> None:
        self.species = SpeciesService(species_root)
        self.presets = PresetService(presets_root, self.species)

    # ------------------------------------------------------------------
    # 物种
    # ------------------------------------------------------------------

    def species_list(self) -> list[SpeciesListItem]:
        return self.species.list()

    def species_get(self, species_id: str) -> SpeciesDetail:
        return self.species.get(species_id)

    def species_create(self, data: SpeciesSkeleton) -> str:
        return self.species.create(data)

    def species_update(self, species_id: str, data: SpeciesSkeleton) -> str:
        return self.species.update(species_id, data)

    def species_delete(self, species_id: str) -> str:
        return self.species.delete(species_id)

    def species_preset_schema(self, species_id: str) -> dict | None:
        return self.species.get_preset_schema(species_id)

    def species_default(self, species_id: str) -> dict | None:
        return self.species.get_default(species_id)

    def species_save_default(self, species_id: str, data: dict) -> str:
        return self.species.save_default(species_id, data)

    # ------------------------------------------------------------------
    # 动作
    # ------------------------------------------------------------------

    def actions_list_all(self) -> list[MotionListItem]:
        return self.species.list_actions_all()

    def action_get(self, species_id: str, action_id: str) -> Motion:
        return self.species.get_action(species_id, action_id)

    def action_create(self, species_id: str, data: Motion) -> str:
        return self.species.save_action(species_id, data.get("motion_id", ""), data)

    def action_update(self, species_id: str, action_id: str, data: Motion) -> str:
        return self.species.save_action(species_id, action_id, data)

    def action_delete(self, species_id: str, action_id: str) -> str:
        return self.species.delete_action(species_id, action_id)

    # ------------------------------------------------------------------
    # 预设
    # ------------------------------------------------------------------

    def presets_list(self) -> list[PresetSummary]:
        return self.presets.list()

    def preset_get(self, preset_id: str) -> dict:
        return self.presets.get(preset_id)

    def preset_new(self, species_id: str) -> dict:
        return self.presets.new_schema(species_id)

    def preset_create(self, data: Preset) -> str:
        return self.presets.create(data)

    def preset_update(self, preset_id: str, data: Preset) -> str:
        return self.presets.update(preset_id, data)

    def preset_delete(self, preset_id: str) -> str:
        return self.presets.delete(preset_id)

    # ------------------------------------------------------------------
    # 3D 渲染
    # ------------------------------------------------------------------

    def render_skeleton3d(self, species_id: str, *, yaw: float = 0, pitch: float = 0,
                          dist: float = 600, zoom: float = 1, pan_x: float = 0, pan_y: float = 0,
                          body: dict | None = None) -> str:
        """3D 骨架渲染（应用体型参数 body），返回 PNG data_url。"""
        from .skeleton3d import build_skeleton_3d, project3d, render_pose, _autofit_transform
        skel3d = build_skeleton_3d(species_id, body=body)
        center = tuple(skel3d.get("center", (480.0, 300.0, 0.0)))
        hr = float(skel3d.get("head_radius", 22.0))
        base = {j: list(v) for j, v in skel3d["joints"].items()}
        base_pts = project3d(base, yaw, pitch, dist, 1.0, center, 0.0, 0.0)
        af = _autofit_transform(base_pts, zoom, pan_x, pan_y)
        img = render_pose(base, skel3d["bones"], yaw, pitch, dist, zoom, center, pan_x, pan_y,
                          autofit=af, head_radius=hr)
        return image_to_data_url(img)

    def render_motion3d(self, action_id: str, *, species: str | None = None, yaw: float = 0,
                        pitch: float = 0, dist: float = 600, zoom: float = 1, pan_x: float = 0,
                        pan_y: float = 0, frame: int = 0, gif: bool = False,
                        frames: bool = False) -> dict:
        """3D 动作渲染。返回 {'data_url'} 或 {'frames':[...],'frame_count'} 或 {'gif':...}。"""
        from .skeleton3d import build_skeleton_3d, pose_3d, project3d, render_pose, _autofit_transform
        from PIL import Image
        if species:
            motion = self.species.get_action(species, action_id)
            species_id = species
        else:
            found = self.species.find_action(action_id)
            if not found:
                raise KeyError(f"3D action not found: {action_id}")
            species_id, motion = found
        skel3d = build_skeleton_3d(species_id)
        center = tuple(skel3d.get("center", (480.0, 300.0, 0.0)))
        hr = float(skel3d.get("head_radius", 22.0))
        n = int(motion.get("frame_count", 8))
        base_pose = pose_3d(skel3d, motion, 0)
        base_pts = project3d(base_pose, yaw, pitch, dist, 1.0, center, 0.0, 0.0)
        af = _autofit_transform(base_pts, zoom, pan_x, pan_y)
        if frames:
            urls = []
            for i in range(n):
                p = pose_3d(skel3d, motion, i)
                urls.append(image_to_data_url(
                    render_pose(p, skel3d["bones"], yaw, pitch, dist, zoom, center, pan_x, pan_y,
                                autofit=af, head_radius=hr)))
            return {"ok": True, "frames": urls, "frame_count": n, "species": species_id}
        if gif:
            imgs = []
            for i in range(n):
                p = pose_3d(skel3d, motion, i)
                imgs.append(render_pose(p, skel3d["bones"], yaw, pitch, dist, zoom, center, pan_x, pan_y,
                                        autofit=af, head_radius=hr).resize((640, 400), Image.Resampling.NEAREST))
            buf = io.BytesIO()
            imgs[0].save(buf, format="GIF", save_all=True, append_images=imgs[1:],
                         duration=180, loop=0, disposal=2)
            return {"ok": True, "gif": "data:image/gif;base64," + base64.b64encode(buf.getvalue()).decode(),
                    "species": species_id}
        p = pose_3d(skel3d, motion, frame)
        img = render_pose(p, skel3d["bones"], yaw, pitch, dist, zoom, center, pan_x, pan_y,
                          autofit=af, head_radius=hr)
        return {"ok": True, "data_url": image_to_data_url(img), "species": species_id}

    def render_preset3d(self, preset_ref: str, *, species: str | None = None,
                        body: dict | None = None, actions: dict | None = None,
                        action_id: str | None = None, yaw: float = 0, pitch: float = 0,
                        dist: float = 600, zoom: float = 1, pan_x: float = 0, pan_y: float = 0,
                        frame: int = 0, gif: bool = False, frames: bool = False) -> dict:
        """3D 预设渲染（应用体型 body + 动作参数 actions）。

        preset_ref='live' 用传参（未保存实时预览），否则读 presets/<id>.json。
        有 action_id → 动作帧/GIF；无 → 骨架。
        """
        from .skeleton3d import build_skeleton_3d, pose_3d, project3d, render_pose, _autofit_transform
        from PIL import Image
        if preset_ref == "live":
            if not species:
                raise ValueError("live preset requires species")
            species_id = species
            b = body or {}
            ac = actions or {}
        else:
            preset = self.presets.get(preset_ref)
            species_id = preset.get("species", "")
            b = preset.get("body") or {}
            ac = preset.get("actions") or {}
        skel3d = build_skeleton_3d(species_id, body=b)
        center = tuple(skel3d.get("center", (480.0, 300.0, 0.0)))
        hr = float(skel3d.get("head_radius", 22.0))
        if action_id:
            motion = self.species.get_action(species_id, action_id)
            n = int(motion.get("frame_count", 8))
            params = (ac or {}).get(action_id, {})
            base_pose = pose_3d(skel3d, motion, 0, params=params)
            base_pts = project3d(base_pose, yaw, pitch, dist, 1.0, center, 0.0, 0.0)
            af = _autofit_transform(base_pts, zoom, pan_x, pan_y)
            if frames:
                urls = []
                for i in range(n):
                    p = pose_3d(skel3d, motion, i, params=params)
                    urls.append(image_to_data_url(
                        render_pose(p, skel3d["bones"], yaw, pitch, dist, zoom, center, pan_x, pan_y,
                                    autofit=af, head_radius=hr)))
                return {"ok": True, "frames": urls, "frame_count": n}
            if gif:
                imgs = []
                for i in range(n):
                    p = pose_3d(skel3d, motion, i, params=params)
                    imgs.append(render_pose(p, skel3d["bones"], yaw, pitch, dist, zoom, center, pan_x, pan_y,
                                            autofit=af, head_radius=hr).resize((640, 400), Image.Resampling.NEAREST))
                buf = io.BytesIO()
                imgs[0].save(buf, format="GIF", save_all=True, append_images=imgs[1:],
                             duration=180, loop=0, disposal=2)
                return {"ok": True, "gif": "data:image/gif;base64," + base64.b64encode(buf.getvalue()).decode()}
            p = pose_3d(skel3d, motion, frame, params=params)
            img = render_pose(p, skel3d["bones"], yaw, pitch, dist, zoom, center, pan_x, pan_y,
                              autofit=af, head_radius=hr)
            return {"ok": True, "data_url": image_to_data_url(img)}
        # 骨架渲染（应用体型）
        base = {j: list(v) for j, v in skel3d["joints"].items()}
        base_pts = project3d(base, yaw, pitch, dist, 1.0, center, 0.0, 0.0)
        af = _autofit_transform(base_pts, zoom, pan_x, pan_y)
        img = render_pose(base, skel3d["bones"], yaw, pitch, dist, zoom, center, pan_x, pan_y,
                          autofit=af, head_radius=hr)
        return {"ok": True, "data_url": image_to_data_url(img)}


# 硬约束：ApiService 必须实现 interfaces.Api 声明的全部操作（运行时校验）
def make_api(species_root: Path, presets_root: Path) -> Api:
    service = ApiService(species_root, presets_root)
    assert isinstance(service, Api), "ApiService 未实现 interfaces.Api 契约（CLI 与 HTTP 将不一致）"
    return service
