#!/usr/bin/env python3
"""AssetsLab HTTP API server.

组装（composition root）各领域模块，只依赖接口：
  species.py     物种模块（自包含：骨架/默认参数/动作/约束）
  skeleton3d.py  3D 骨架/动作引擎（读物种默认参数渲染）
  motion.py      3D 动作 DSL 求值器
  render.py      3D 绘制原语

API（仅 3D，基于物种默认参数）:
  /api/species            — 物种 (CRUD) + /default 默认参数读写
  /api/skeleton3d/<sp>    — 3D 骨架任意视角 PNG（基于物种默认参数）
  /api/motion3d/<action>  — 3D 动作帧/GIF（基于物种默认参数）

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

from assetslab.interfaces import SpeciesModule
from assetslab.species import SpeciesService

# ---- paths ----
PKG_ROOT = _PKG_ROOT
WEB_DIST = PKG_ROOT / "web" / "dist"


# 2D 遗留渲染服务（方案 A）已移除：3D 渲染由 skeleton3d 提供，无 2D 引擎。


class AssetsLabHandler(SimpleHTTPRequestHandler):
    """HTTP 处理器。依赖注入：species / presets 两个服务。"""

    server_version = "AssetsLab/2.0"

    # 注入的依赖（由 build_server 设置）
    species: SpeciesModule = None        # type: ignore[assignment]

    def log_message(self, format: str, *args: object) -> None:
        return  # silent

    # -- routing -------------------------------------------------------

    def do_GET(self) -> None:
        p = self.path
        if p.startswith("/api/species"):
            return self._species_get()
        if p == "/api/motions3d":
            return self._motions3d_list()
        if p.startswith("/api/motion3d/"):
            return self._motion3d_get()
        if p.startswith("/api/skeleton3d/"):
            return self._skeleton3d_get()
        if p.startswith("/api/"):
            return self._json({"ok": False, "error": "api not found"}, 404)
        return self._serve_static()

    def do_POST(self) -> None:
        p = self.path
        if p.startswith("/api/species"):
            return self._species_post()
        self.send_error(404)

    def do_PUT(self) -> None:
        if p := self.path:
            if p.startswith("/api/species/"):
                return self._species_post()
        self.send_error(404)

    def do_DELETE(self) -> None:
        if self.path.startswith("/api/species/"):
            return self._species_delete()

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
        """GET /api/skeleton3d/<species_id>?yaw=45&pitch=12&dist=600&zoom=1&<body 参数> — 3D 骨架任意角度/距离 PNG（基于物种默认参数）。"""
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
        # 其余查询参数作为体型参数（param_chains 驱动，3D 空间应用）
        cam_keys = {"yaw", "pitch", "dist", "zoom", "pan_x", "pan_y"}
        body = {k: float(v[0]) for k, v in qs.items() if k not in cam_keys}
        species_id = parts[0]
        try:
            from assetslab.skeleton3d import build_skeleton_3d, render_view
            skel3d = build_skeleton_3d(species_id, body or None)
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
        species_q = qs.get("species", [None])[0]
        try:
            from assetslab.skeleton3d import build_skeleton_3d, pose_3d, render_pose
            # 从 species actions3d 扫描动作；可指定 species=<id> 限定范围（数据驱动，不硬编码）
            species_id = None
            path = None
            for sp_dir in (_PKG_ROOT / "species").iterdir():
                if species_q and sp_dir.name != species_q:
                    continue
                cand = sp_dir / "actions3d" / f"{parts[0]}.json"
                if cand.exists():
                    species_id, path = sp_dir.name, cand
                    break
            if path is None:
                return self._json({"ok": False, "error": f"3D action not found: {parts[0]}"}, 404)
            m3d = json.load(open(path))
            # 基于物种默认参数构建骨架（数据驱动，不依赖预设）
            skel3d = build_skeleton_3d(species_id)
            center = tuple(skel3d.get("center", (480.0, 300.0, 0.0)))
            n = int(m3d.get("frame_count", 8))
            # 用首帧计算一次固定 autofit，多帧输出（GIF/frames）共用，避免逐帧缩放抖动
            from assetslab.skeleton3d import _autofit_transform, project3d
            base_pose = pose_3d(skel3d, m3d, 0)
            base_pts = project3d(base_pose, yaw, pitch, dist, 1.0, center, 0.0, 0.0)
            af = _autofit_transform(base_pts, zoom, pan_x, pan_y)
            # frames=1：返回全部帧 PNG（前端 JS 轮播，动画与浏览器 GIF 播放无关，最可靠）
            if qs.get("frames", ["0"])[0] in ("1", "true"):
                hr = float(skel3d.get("head_radius", 22.0))
                frame_urls = []
                for i in range(n):
                    p = pose_3d(skel3d, m3d, i)
                    img = render_pose(p, skel3d["bones"], yaw, pitch, dist, zoom, center, pan_x, pan_y, autofit=af, head_radius=hr)
                    frame_urls.append(_image_to_data_url(img))
                return self._json({"ok": True, "frames": frame_urls, "frame_count": n})
            if gif:
                from PIL import Image
                hr = float(skel3d.get("head_radius", 22.0))
                frames = []
                for i in range(n):
                    p = pose_3d(skel3d, m3d, i)
                    frames.append(render_pose(p, skel3d["bones"], yaw, pitch, dist, zoom, center, pan_x, pan_y, autofit=af, head_radius=hr).resize((640, 400), Image.Resampling.NEAREST))
                buf = io.BytesIO()
                frames[0].save(buf, format="GIF", save_all=True, append_images=frames[1:],
                               duration=180, loop=0, disposal=2)
                return self._json({"ok": True, "gif": "data:image/gif;base64," + base64.b64encode(buf.getvalue()).decode()})
            pose = pose_3d(skel3d, m3d, frame)
            img = render_pose(pose, skel3d["bones"], yaw, pitch, dist, zoom, center, pan_x, pan_y, autofit=af, head_radius=float(skel3d.get("head_radius", 22.0)))
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
            # HTML 始终不缓存（前端构建后刷新即生效）；带 hash 的静态资源保持缓存
            if file_path.suffix == ".html":
                self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(file_path.read_bytes())
            return
        # SPA fallback
        index = WEB_DIST / "index.html"
        if index.is_file():
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(index.stat().st_size))
            self.send_header("Cache-Control", "no-cache")
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
        # 预设 schema：GET /api/species/<id>/preset_schema
        if len(parts) >= 2 and parts[1] == "preset_schema":
            schema = self.species.get_preset_schema(sp_id)
            if schema is None:
                return self._json({"ok": False, "error": f"preset_schema not found: {sp_id}"}, 404)
            return self._json(schema)
        # 默认参数：GET /api/species/<id>/default
        if len(parts) >= 2 and parts[1] == "default":
            try:
                return self._json(self.species.get_default(sp_id))
            except KeyError:
                return self._json({"ok": False, "error": f"default not found: {sp_id}"}, 404)
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
        # 默认参数保存：POST/PUT /api/species/<id>/default
        if len(parts) >= 2 and parts[1] == "default":
            try:
                self.species.save_default(sp_id, body)
            except Exception as e:
                return self._json({"ok": False, "error": str(e)}, 400)
            return self._json({"ok": True, "saved": sp_id})
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

    handler = type(
        "InjectedHandler",
        (AssetsLabHandler,),
        {
            "species": species,
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
