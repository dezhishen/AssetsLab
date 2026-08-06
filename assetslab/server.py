#!/usr/bin/env python3
"""AssetsLab HTTP API server.

组装（composition root）各领域模块，只依赖接口：
  species.py   物种模块（自包含）
  preset.py    预设模块（依赖物种模块接口）
  motion.py    动作模块（依赖物种模块接口）
  render.py    骨架绘制模块

API:
  /api/species     — 物种 (CRUD)
  /api/skeletons   — 预设 (list, detail, render, save)
  /api/motions     — 动作 (list, render)

Usage:
  python assetslab/server.py --port 8765
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote
from typing import Protocol

# Make 'assetslab' package importable when run as `python assetslab/server.py`
_PKG_ROOT = Path(__file__).resolve().parent  # assetslab/
_REPO_ROOT = _PKG_ROOT.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from assetslab import motion as motion_mod
from assetslab import render as render_mod
from assetslab.interfaces import PresetModule, RenderService, SpeciesModule
from assetslab.preset import PresetService
from assetslab.species import SpeciesService

# ---- paths ----
PKG_ROOT = _PKG_ROOT
WEB_DIST = PKG_ROOT / "web" / "dist"


class _RenderService:
    """渲染服务实现（组装根内部适配器）。

    将 render.py（骨架绘制）与 motion.py（动作引擎）封装成 RenderService 接口。
    放在组装根，不单独成层。
    """

    def skeleton_preview(self, skeleton_id: str, view: str, body_overrides=None):
        render_mod.set_skeleton(skeleton_id)
        base = None
        if body_overrides:
            # 体型参数实时覆盖：对目标视图坐标应用比例，无需先保存预设
            try:
                views = render_mod.skeleton_views()
                if view in views:
                    coords = {k: [float(x), float(y)] for k, (x, y) in views[view].items()}
                    motion_mod.apply_proportions(coords, body_overrides, view)
                    base = {k: (float(v[0]), float(v[1])) for k, v in coords.items()}
            except Exception:
                base = None
        return render_mod.render_frame(view, "skeleton", 0, 1.0, 1.0, 1.0, base=base)

    def motion_frame(self, motion_id: str, *, view="front", stage="arms",
                     skeleton="standard", frame_index=0,
                     overrides=None, proportions=None):
        motion = motion_mod.load_motion(motion_id)
        motion_mod.set_skeleton(skeleton)
        # 动作定义了 IK 链就启用 IK（保证腿长恒定，hip/knee/foot 联动）
        use_ik = bool(motion.get("ik"))
        return motion_mod.render_frame(
            motion, view, stage, int(frame_index),
            overrides or None, use_ik, proportions or None,
        )


class AssetsLabHandler(SimpleHTTPRequestHandler):
    """HTTP 处理器。依赖注入：species / presets / render 三个服务。"""

    server_version = "AssetsLab/2.0"

    # 注入的依赖（由 build_server 设置）
    species: SpeciesModule = None        # type: ignore[assignment]
    presets: PresetModule = None         # type: ignore[assignment]
    render: RenderService = None         # type: ignore[assignment]

    def log_message(self, format: str, *args: object) -> None:
        return  # silent

    # -- routing -------------------------------------------------------

    def do_GET(self) -> None:
        p = self.path
        if p.startswith("/api/species"):
            return self._species_get()
        if p.startswith("/api/skeletons"):
            return self._skeletons_get()
        if p == "/api/motions3d":
            return self._motions3d_list()
        if p.startswith("/api/motion3d/"):
            return self._motion3d_get()
        if p.startswith("/api/skeleton3d/"):
            return self._skeleton3d_get()
        if p.startswith("/api/motions"):
            return self._motions_get()
        return self._serve_static()

    def do_POST(self) -> None:
        p = self.path
        if p.startswith("/api/species"):
            return self._species_post()
        if p == "/api/skeletons" or p.startswith("/api/skeletons/"):
            return self._skeletons_post()
        if p.startswith("/api/motions/"):
            return self._motions_post()
        self.send_error(404)

    def do_PUT(self) -> None:
        if p := self.path:
            if p.startswith("/api/skeletons/"):
                return self._skeletons_post()
            if p.startswith("/api/species/"):
                return self._species_post()
        self.send_error(404)

    def do_DELETE(self) -> None:
        if self.path.startswith("/api/species/"):
            return self._species_delete()
        if self.path.startswith("/api/skeletons/"):
            return self._skeleton_delete()

    # -- 3D API ---------------------------------------------------------
    # 阶段 1/2：3D 骨架 + 3D 动作，任意视角（yaw）正交投影。

    def _motions3d_list(self) -> None:
        """GET /api/motions3d — 列出所有物种的 3D 动作（含 params，供前端参数滑块）。"""
        items = []
        for sp_dir in (_PKG_ROOT / "species").iterdir():
            ad = sp_dir / "actions3d"
            if not ad.is_dir():
                continue
            for p in sorted(ad.glob("*.json")):
                try:
                    data = json.load(open(p))
                    items.append({
                        "motion_id": data.get("motion_id", p.stem),
                        "title": data.get("title", p.stem),
                        "description": data.get("description", ""),
                        "species": data.get("species", sp_dir.name),
                        "params": data.get("params", {}),
                        "has_ik": bool(data.get("ik3d")),
                    })
                except Exception:
                    continue
        return self._json({"motions3d": items})

    def _skeleton3d_get(self) -> None:
        """GET /api/skeleton3d/<preset_id>?yaw=45&pitch=12&dist=600&zoom=1 — 3D 骨架任意角度/距离 PNG。"""
        from urllib.parse import parse_qs, urlparse
        path_only = urlparse(self.path).path
        parts = _path_parts(path_only, "/api/skeleton3d")
        if len(parts) != 1:
            self.send_error(404)
            return
        qs = parse_qs(urlparse(self.path).query)
        yaw = float(qs.get("yaw", ["0"])[0])
        pitch = float(qs.get("pitch", ["0"])[0])
        dist = float(qs.get("dist", ["600"])[0])
        zoom = float(qs.get("zoom", ["1"])[0])
        pan_x = float(qs.get("pan_x", ["0"])[0])
        pan_y = float(qs.get("pan_y", ["0"])[0])
        try:
            from assetslab.skeleton3d import build_skeleton_3d, render_view
            skel3d = build_skeleton_3d(parts[0])
            img = render_view(skel3d, yaw, pitch, dist, zoom, pan_x, pan_y)
            return self._json({"ok": True, "data_url": _image_to_data_url(img)})
        except Exception as e:
            return self._json({"ok": False, "error": str(e)}, 500)

    def _motion3d_get(self) -> None:
        """GET /api/motion3d/<action_id>?yaw=45&pitch=12&dist=600&frame=0[&gif=1] — 3D 动作帧/GIF。"""
        from urllib.parse import parse_qs, urlparse
        path_only = urlparse(self.path).path
        parts = _path_parts(path_only, "/api/motion3d")
        if len(parts) != 1:
            self.send_error(404)
            return
        qs = parse_qs(urlparse(self.path).query)
        yaw = float(qs.get("yaw", ["0"])[0])
        pitch = float(qs.get("pitch", ["0"])[0])
        dist = float(qs.get("dist", ["600"])[0])
        zoom = float(qs.get("zoom", ["1"])[0])
        pan_x = float(qs.get("pan_x", ["0"])[0])
        pan_y = float(qs.get("pan_y", ["0"])[0])
        frame = int(qs.get("frame", ["0"])[0])
        gif = qs.get("gif", ["0"])[0] in ("1", "true")
        try:
            from assetslab.skeleton3d import build_skeleton_3d, pose_3d, render_pose
            # 从所有物种的 actions3d 扫描动作（不硬编码物种/路径）
            species_id = None
            path = None
            for sp_dir in (_PKG_ROOT / "species").iterdir():
                cand = sp_dir / "actions3d" / f"{parts[0]}.json"
                if cand.exists():
                    species_id, path = sp_dir.name, cand
                    break
            if path is None:
                return self._json({"ok": False, "error": f"3D action not found: {parts[0]}"}, 404)
            m3d = json.load(open(path))
            skel3d = build_skeleton_3d("standard", species_id)
            center = tuple(skel3d.get("center", (480.0, 300.0, 0.0)))
            if gif:
                from PIL import Image
                frames = []
                for i in range(int(m3d.get("frame_count", 8))):
                    pose = pose_3d(skel3d, m3d, i)
                    frames.append(render_pose(pose, skel3d["bones"], yaw, pitch, dist, zoom, center, pan_x, pan_y).resize((480, 300), Image.Resampling.NEAREST))
                buf = io.BytesIO()
                frames[0].save(buf, format="GIF", save_all=True, append_images=frames[1:],
                               duration=180, loop=0, disposal=2)
                return self._json({"ok": True, "gif": "data:image/gif;base64," + base64.b64encode(buf.getvalue()).decode()})
            pose = pose_3d(skel3d, m3d, frame)
            img = render_pose(pose, skel3d["bones"], yaw, pitch, dist, zoom, center, pan_x, pan_y)
            return self._json({"ok": True, "data_url": _image_to_data_url(img)})
        except Exception as e:
            return self._json({"ok": False, "error": str(e)}, 500)

    # -- static files --------------------------------------------------

    def _serve_static(self) -> None:
        """Serve the Vue SPA: try WEB_DIST, fallback to index.html."""
        path = self.path.lstrip("/")
        if not path:
            path = "index.html"
        file_path = WEB_DIST / path
        if file_path.is_file():
            content_type = _mime(path)
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(file_path.stat().st_size))
            self.end_headers()
            self.wfile.write(file_path.read_bytes())
            return
        # SPA fallback
        index = WEB_DIST / "index.html"
        if index.is_file():
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(index.stat().st_size))
            self.end_headers()
            self.wfile.write(index.read_bytes())
        else:
            self.send_error(404, "Frontend not built. Run: cd assetslab/web && npm run build")

    # -- species API ---------------------------------------------------

    def _species_get(self) -> None:
        """GET /api/species — list; /api/species/<id> — detail; .../actions/<aid> — action."""
        parts = _path_parts(self.path, "/api/species")
        if not parts:
            return self._json({"species": self.species.list()})

        sp_id = parts[0]
        # 动作详情：GET /api/species/<id>/actions/<action_id>
        if len(parts) >= 3 and parts[1] == "actions":
            action_id = parts[2]
            try:
                return self._json(self.species.get_action(sp_id, action_id))
            except KeyError:
                return self._json({"ok": False, "error": f"action not found: {sp_id}/{action_id}"}, 404)

        try:
            return self._json(self.species.get(sp_id))
        except KeyError:
            return self._json({"ok": False, "error": f"species not found: {sp_id}"}, 404)

    def _species_post(self) -> None:
        """POST /api/species — create; PUT /api/species/<id> — update;
        POST .../actions — create action; PUT .../actions/<aid> — update action."""
        parts = _path_parts(self.path, "/api/species")
        try:
            body = self._read_body()
        except Exception as e:
            return self._json({"ok": False, "error": str(e)}, 400)

        if not parts:
            # 创建物种
            try:
                sp_id = self.species.create(body)
            except FileExistsError as e:
                return self._json({"ok": False, "error": str(e)}, 409)
            except (ValueError, KeyError) as e:
                return self._json({"ok": False, "error": str(e)}, 400)
            return self._json({"ok": True, "created": sp_id})

        sp_id = parts[0]
        # 动作路由：POST /api/species/<id>/actions 或 PUT .../actions/<aid>
        if len(parts) >= 2 and parts[1] == "actions":
            action_id = body.get("motion_id", "").strip() if len(parts) == 2 else parts[2]
            if not action_id:
                return self._json({"ok": False, "error": "action_id required"}, 400)
            try:
                saved = self.species.save_action(sp_id, action_id, body)
            except Exception as e:
                return self._json({"ok": False, "error": str(e)}, 400)
            return self._json({"ok": True, "saved": saved})

        # 更新物种
        try:
            sp_id = self.species.update(sp_id, body)
        except Exception as e:
            return self._json({"ok": False, "error": str(e)}, 400)
        return self._json({"ok": True, "updated": sp_id})

    def _species_delete(self) -> None:
        """DELETE /api/species/<id> — delete species; .../actions/<aid> — delete action."""
        parts = _path_parts(self.path, "/api/species")
        if not parts:
            return self._json({"ok": False, "error": "missing id"}, 400)

        sp_id = parts[0]
        # 删除动作：DELETE /api/species/<id>/actions/<action_id>
        if len(parts) >= 3 and parts[1] == "actions":
            action_id = parts[2]
            try:
                self.species.delete_action(sp_id, action_id)
            except KeyError:
                return self._json({"ok": False, "error": f"action not found: {sp_id}/{action_id}"}, 404)
            return self._json({"ok": True, "deleted": action_id})

        # 删除物种
        try:
            sp_id = self.species.delete(sp_id)
        except KeyError:
            return self._json({"ok": False, "error": f"species not found: {parts[0]}"}, 404)
        return self._json({"ok": True, "deleted": sp_id})

    # -- skeletons (presets) API ---------------------------------------

    def _skeletons_get(self) -> None:
        """GET /api/skeletons — list; GET /api/skeletons/<id> — detail with species merge."""
        parts = _path_parts(self.path, "/api/skeletons")
        if not parts:
            return self._json({"skeletons": self.presets.list(), "species": []})
        try:
            return self._json(self.presets.get(parts[0]))
        except KeyError:
            return self._json({"ok": False, "error": f"skeleton not found: {parts[0]}"}, 404)

    def _skeletons_post(self) -> None:
        """POST /api/skeletons — create preset;
        POST /api/skeletons/<id>/render | /api/skeletons/<id>/save"""
        parts = _path_parts(self.path, "/api/skeletons")
        if not parts:
            # 创建预设
            try:
                data = self._read_body()
                preset_id = self.presets.create(data)
            except FileExistsError as e:
                return self._json({"ok": False, "error": str(e)}, 409)
            except Exception as e:
                return self._json({"ok": False, "error": str(e)}, 400)
            return self._json({"ok": True, "created": preset_id})
        if len(parts) == 2 and parts[1] == "render":
            return self._skeleton_render(parts[0])
        if len(parts) == 2 and parts[1] == "save":
            return self._skeleton_save(parts[0])
        self.send_error(404)

    def _skeleton_delete(self) -> None:
        """DELETE /api/skeletons/<id> — delete preset."""
        parts = _path_parts(self.path, "/api/skeletons")
        if not parts:
            return self._json({"ok": False, "error": "missing id"}, 400)
        try:
            preset_id = self.presets.delete(parts[0])
        except KeyError:
            return self._json({"ok": False, "error": f"skeleton not found: {parts[0]}"}, 404)
        return self._json({"ok": True, "deleted": preset_id})

    def _skeleton_render(self, skel_id: str) -> None:
        try:
            body = self._read_body()
        except Exception as e:
            return self._json({"ok": False, "error": str(e)}, 400)
        try:
            view = str(body.get("view", "front"))
            # 体型参数覆盖支持两种传法：顶层 {head_scale:..} 或嵌套 {body:{head_scale:..}}
            overrides_src = body.get("body") if isinstance(body.get("body"), dict) else body
            body_overrides = _float_map(overrides_src, motion_mod.PROPORTION_NAMES) or None
            img = self.render.skeleton_preview(skel_id, view, body_overrides)
            return self._json({"ok": True, "data_url": _image_to_data_url(img)})
        except Exception as e:
            return self._json({"ok": False, "error": str(e)}, 500)

    def _skeleton_save(self, skel_id: str) -> None:
        """Save preset, stripping species-merged data (only preset's own fields)."""
        try:
            data = self._read_body()
        except Exception as e:
            return self._json({"ok": False, "error": str(e)}, 400)
        # 只保留预设自身字段，去掉从物种合并来的数据（bones/joints/chains/param_chains/torso_inherit）
        preset_own = {
            k: v for k, v in data.items()
            if k not in ("bones", "joints", "chains", "param_chains", "torso_inherit")
        }
        try:
            saved = self.presets.save(skel_id, preset_own)
        except Exception as e:
            return self._json({"ok": False, "error": str(e)}, 400)
        return self._json({"ok": True, "saved": saved})

    # -- motions API ---------------------------------------------------

    def _motions_get(self) -> None:
        """GET /api/motions — list all motions from species/<id>/actions/."""
        return self._json({"motions": self.species.list_actions_all()})

    def _motions_post(self) -> None:
        """POST /api/motions/<id>/render — render a motion frame."""
        parts = _path_parts(self.path, "/api/motions")
        if len(parts) != 2 or parts[1] != "render":
            self.send_error(404)
            return
        motion_id = parts[0]
        try:
            body = self._read_body()
        except Exception as e:
            return self._json({"ok": False, "error": str(e)}, 400)
        try:
            # 动态获取该动作的全部参数名，允许前端传任意动作参数（含 intensity）
            motion_def = self.species.find_action(motion_id)
            motion_param_names = tuple(motion_def[1].get("params", {}).keys()) if motion_def else ("intensity", "stride", "pelvis_bob", "arm_swing")
            overrides = _float_map(body, motion_param_names)
            proportions = _float_map(body, (
                "head_scale", "neck_length", "torso_length",
                "shoulder_width", "upper_arm_length", "forearm_length",
                "thigh_length", "shin_length",
            ))

            # 动画循环预览（GIF）——参数变化在此可见；单帧只在显式传 frame_index 时返回
            if body.get("gif") or body.get("frame_index") is None:
                gif_url = self._render_motion_gif(
                    motion_id, view=str(body.get("view", "front")),
                    stage=str(body.get("stage", "arms")),
                    skeleton=str(body.get("skeleton", "standard")),
                    overrides=overrides, proportions=proportions,
                )
                return self._json({"ok": True, "gif": gif_url})

            img = self.render.motion_frame(
                motion_id,
                view=str(body.get("view", "front")),
                stage=str(body.get("stage", "arms")),
                skeleton=str(body.get("skeleton", "standard")),
                frame_index=int(body.get("frame_index", 0)),
                overrides=overrides,
                proportions=proportions,
            )
            return self._json({"ok": True, "frame": _image_to_data_url(img)})
        except Exception as e:
            return self._json({"ok": False, "error": str(e)}, 500)

    def _render_motion_gif(self, motion_id: str, *, view: str, stage: str,
                           skeleton: str, overrides: dict | None, proportions: dict | None) -> str:
        """渲染完整动作循环为 GIF 数据 URL（参数变化可见）。"""
        from PIL import Image

        motion = motion_mod.load_motion(motion_id)
        motion_mod.set_skeleton(skeleton)
        # 动作定义了 IK 就启用（腿长恒定，hip/knee/foot 联动）
        use_ik = bool(motion.get("ik"))
        frames = motion_mod.render_motion(motion, view, stage, overrides or None, use_ik, None, 0.0, proportions or None)
        # 缩放到合理大小
        scaled = [f.resize((480, 300), Image.Resampling.NEAREST) for f in frames]
        buf = io.BytesIO()
        scaled[0].save(buf, format="GIF", save_all=True, append_images=scaled[1:],
                       duration=125, loop=0, disposal=2)
        return "data:image/gif;base64," + base64.b64encode(buf.getvalue()).decode()

    # -- helpers -------------------------------------------------------

    def _json(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length))


# ---- utility ------------------------------------------------------------


def _path_parts(path: str, prefix: str) -> list[str]:
    return [unquote(p) for p in path[len(prefix):].rstrip("/").split("/") if p]


def _image_to_data_url(img) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _float_map(body: dict, keys: tuple[str, ...]) -> dict[str, float]:
    out: dict[str, float] = {}
    for k in keys:
        if body.get(k) is not None:
            out[k] = float(body[k])
    return out


_MIME_MAP = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
}


def _mime(path: str) -> str:
    return _MIME_MAP.get(Path(path).suffix.lower(), "application/octet-stream")


# ---- main ---------------------------------------------------------------


def build_server(port: int = 8765, host: str = "0.0.0.0"):
    """组装服务器：依赖注入各领域模块。

    唯一的组装根：在这里实例化具体模块并注入到 Handler。
    其余代码一律只依赖接口。
    """
    # 领域模块
    species = SpeciesService(PKG_ROOT / "species")
    presets = PresetService(PKG_ROOT / "presets", species)

    # 动作模块依赖物种模块（动作属于物种）
    motion_mod.set_species_module(species)

    # 渲染服务（封装 render.py + motion.py）
    render = _RenderService()

    handler = type(
        "InjectedHandler",
        (AssetsLabHandler,),
        {
            "species": species,
            "presets": presets,
            "render": render,
        },
    )
    return ThreadingHTTPServer((host, port), handler)


def main():
    parser = argparse.ArgumentParser(description="AssetsLab API Server")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()

    if not (WEB_DIST / "index.html").is_file():
        print("Warning: web/dist not found. Run: cd assetslab/web && npm run build", file=sys.stderr)

    server = build_server(args.port, args.host)
    print(f"AssetsLab server: http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
