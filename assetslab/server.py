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
import json
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

# Make 'assetslab' package importable when run as `python assetslab/server.py`
_PKG_ROOT = Path(__file__).resolve().parent  # assetslab/
_REPO_ROOT = _PKG_ROOT.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from assetslab.interfaces import Api
from assetslab.api import ApiService
from assetslab.config import DEFAULT_DATA_DIR, ensure_species_seeded

# ---- paths ----
PKG_ROOT = _PKG_ROOT
_BUNDLE = getattr(sys, "_MEIPASS", None)
WEB_DIST = (Path(_BUNDLE) / "web" / "dist") if _BUNDLE else (PKG_ROOT / "web" / "dist")


class AssetsLabHandler(SimpleHTTPRequestHandler):
    """HTTP 处理器。依赖注入：统一 Api 服务（CLI 与 HTTP 共用同一套接口）。"""

    server_version = "AssetsLab/2.0"

    # 注入的依赖（由 build_server 设置）
    api: Api = None        # type: ignore[assignment]
    dev_mode: bool = False

    def end_headers(self) -> None:
        """开发模式（--dev）下追加 CORS 头，供前端 Vite dev / proxy 跨域。"""
        if self.dev_mode:
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return  # silent

    # -- routing -------------------------------------------------------

    def do_GET(self) -> None:
        p = self.path
        if p.startswith("/api/species"):
            return self._species_get()
        if p.startswith("/api/preset3d/"):
            return self._preset3d_get()
        if p.startswith("/api/presets"):
            return self._presets_get()
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
        if p.startswith("/api/presets"):
            return self._presets_post()
        self.send_error(404)

    def do_PUT(self) -> None:
        if p := self.path:
            if p.startswith("/api/species/"):
                return self._species_post()
            if p.startswith("/api/presets"):
                return self._presets_post()
        self.send_error(404)

    def do_DELETE(self) -> None:
        if self.path.startswith("/api/species/"):
            return self._species_delete()
        if self.path.startswith("/api/presets"):
            return self._presets_delete()

    # -- 3D API ---------------------------------------------------------
    # 阶段 1/2：3D 骨架 + 3D 动作，任意视角（yaw）正交投影。

    def _motions3d_list(self) -> None:
        """GET /api/motions3d — 列出所有物种的 3D 动作（含 params，供前端参数滑块）。"""
        return self._json({"motions3d": self.api.actions_list_all()})

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
            data_url = self.api.render_skeleton3d(
                species_id, yaw=yaw, pitch=pitch, dist=dist, zoom=zoom,
                pan_x=pan_x, pan_y=pan_y, body=body or None)
            return self._json({"ok": True, "data_url": data_url})
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
            result = self.api.render_motion3d(
                parts[0], species=species_q, yaw=yaw, pitch=pitch, dist=dist, zoom=zoom,
                pan_x=pan_x, pan_y=pan_y, frame=frame, gif=gif,
                frames=qs.get("frames", ["0"])[0] in ("1", "true"))
            return self._json(result)
        except KeyError as e:
            return self._json({"ok": False, "error": str(e)}, 404)
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
            return self._json({"species": self.api.species_list()})

        sp_id = parts[0]
        # 预设 schema：GET /api/species/<id>/preset_schema
        if len(parts) >= 2 and parts[1] == "preset_schema":
            schema = self.api.species_preset_schema(sp_id)
            if schema is None:
                return self._json({"ok": False, "error": f"preset_schema not found: {sp_id}"}, 404)
            return self._json(schema)
        # 默认参数：GET /api/species/<id>/default
        if len(parts) >= 2 and parts[1] == "default":
            try:
                return self._json(self.api.species_default(sp_id))
            except KeyError:
                return self._json({"ok": False, "error": f"default not found: {sp_id}"}, 404)
        # 动作详情：GET /api/species/<id>/actions/<action_id>
        if len(parts) >= 3 and parts[1] == "actions":
            action_id = parts[2]
            try:
                return self._json(self.api.action_get(sp_id, action_id))
            except KeyError:
                return self._json({"ok": False, "error": f"action not found: {sp_id}/{action_id}"}, 404)

        try:
            return self._json(self.api.species_get(sp_id))
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
                sp_id = self.api.species_create(body)
            except FileExistsError as e:
                return self._json({"ok": False, "error": str(e)}, 409)
            except (ValueError, KeyError) as e:
                return self._json({"ok": False, "error": str(e)}, 400)
            return self._json({"ok": True, "created": sp_id})

        sp_id = parts[0]
        # 默认参数保存：POST/PUT /api/species/<id>/default
        if len(parts) >= 2 and parts[1] == "default":
            try:
                self.api.species_save_default(sp_id, body)
            except Exception as e:
                return self._json({"ok": False, "error": str(e)}, 400)
            return self._json({"ok": True, "saved": sp_id})
        # 动作路由：POST /api/species/<id>/actions 或 PUT .../actions/<aid>
        if len(parts) >= 2 and parts[1] == "actions":
            action_id = body.get("motion_id", "").strip() if len(parts) == 2 else parts[2]
            if not action_id:
                return self._json({"ok": False, "error": "action_id required"}, 400)
            try:
                saved = self.api.action_create(sp_id, body) if len(parts) == 2 else self.api.action_update(sp_id, action_id, body)
            except Exception as e:
                return self._json({"ok": False, "error": str(e)}, 400)
            return self._json({"ok": True, "saved": saved})

        # 更新物种
        try:
            sp_id = self.api.species_update(sp_id, body)
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
                self.api.action_delete(sp_id, action_id)
            except KeyError:
                return self._json({"ok": False, "error": f"action not found: {sp_id}/{action_id}"}, 404)
            return self._json({"ok": True, "deleted": action_id})

        # 删除物种
        try:
            sp_id = self.api.species_delete(sp_id)
        except KeyError:
            return self._json({"ok": False, "error": f"species not found: {parts[0]}"}, 404)
        return self._json({"ok": True, "deleted": sp_id})

    # -- helpers -------------------------------------------------------

    # -- presets API ---------------------------------------------------

    def _presets_get(self) -> None:
        """GET /api/presets — list; /api/presets/new?species= — 新建空白表单; /api/presets/<id> — 详情。"""
        from urllib.parse import urlparse
        parts = _path_parts(urlparse(self.path).path, "/api/presets")
        if not parts:
            return self._json({"presets": self.api.presets_list()})
        if parts[0] == "new":
            from urllib.parse import parse_qs, urlparse
            qs = parse_qs(urlparse(self.path).query)
            sp = qs.get("species", ["human"])[0]
            try:
                return self._json(self.api.preset_new(sp))
            except Exception as e:
                return self._json({"ok": False, "error": str(e)}, 400)
        try:
            return self._json(self.api.preset_get(parts[0]))
        except KeyError:
            return self._json({"ok": False, "error": f"preset not found: {parts[0]}"}, 404)

    def _presets_post(self) -> None:
        """POST /api/presets — create; PUT /api/presets/<id> — update。"""
        from urllib.parse import urlparse
        parts = _path_parts(urlparse(self.path).path, "/api/presets")
        try:
            body = self._read_body()
        except Exception as e:
            return self._json({"ok": False, "error": str(e)}, 400)
        if not parts:
            try:
                pid = self.api.preset_create(body)
            except FileExistsError as e:
                return self._json({"ok": False, "error": str(e)}, 409)
            except (ValueError, KeyError) as e:
                return self._json({"ok": False, "error": str(e)}, 400)
            return self._json({"ok": True, "created": pid})
        try:
            pid = self.api.preset_update(parts[0], body)
        except KeyError:
            return self._json({"ok": False, "error": f"preset not found: {parts[0]}"}, 404)
        except Exception as e:
            return self._json({"ok": False, "error": str(e)}, 400)
        return self._json({"ok": True, "updated": pid})

    def _presets_delete(self) -> None:
        """DELETE /api/presets/<id> — delete preset。"""
        from urllib.parse import urlparse
        parts = _path_parts(urlparse(self.path).path, "/api/presets")
        if not parts:
            return self._json({"ok": False, "error": "missing id"}, 400)
        try:
            self.api.preset_delete(parts[0])
        except KeyError:
            return self._json({"ok": False, "error": f"preset not found: {parts[0]}"}, 404)
        return self._json({"ok": True, "deleted": parts[0]})

    def _preset3d_get(self) -> None:
        """GET /api/preset3d/<id> 或 /api/preset3d/live — 预设渲染（骨架/动作）。

        - <id>: 读 presets/<id>.json（body 体型参数 + actions 动作参数）
        - live: 用 query 直接传参渲染（未保存的编辑实时预览）
          ?species=human&body=<json>&actions=<json>[&action=walk3d]
        不传 action → 渲染骨架（应用体型参数）。
        """
        from urllib.parse import parse_qs, urlparse
        parts = _path_parts(urlparse(self.path).path, "/api/preset3d")
        if len(parts) != 1:
            return self._json({"ok": False, "error": "preset id or 'live' required"}, 400)
        qs = parse_qs(urlparse(self.path).query)
        yaw = float(qs.get("yaw", ["0"])[0])
        pitch = float(qs.get("pitch", ["0"])[0])
        dist = float(qs.get("dist", ["600"])[0])
        zoom = float(qs.get("zoom", ["1"])[0])
        pan_x = float(qs.get("pan_x", ["0"])[0])
        pan_y = float(qs.get("pan_y", ["0"])[0])
        frame = int(qs.get("frame", ["0"])[0])
        gif = qs.get("gif", ["0"])[0] in ("1", "true")
        frames = qs.get("frames", ["0"])[0] in ("1", "true")
        action_id = qs.get("action", [None])[0]
        try:
            if parts[0] == "live":
                species_id = qs.get("species", [None])[0]
                if not species_id:
                    return self._json({"ok": False, "error": "live preset requires species"}, 400)
                body = json.loads(qs.get("body", ["{}"])[0])
                actions = json.loads(qs.get("actions", ["{}"])[0])
            else:
                species_id = None
                body = None
                actions = None
        except json.JSONDecodeError as e:
            return self._json({"ok": False, "error": str(e)}, 400)
        try:
            result = self.api.render_preset3d(
                parts[0], species=species_id, body=body, actions=actions,
                action_id=action_id, yaw=yaw, pitch=pitch, dist=dist, zoom=zoom,
                pan_x=pan_x, pan_y=pan_y, frame=frame, gif=gif, frames=frames)
            return self._json(result)
        except KeyError as e:
            return self._json({"ok": False, "error": str(e)}, 404)
        except Exception as e:
            return self._json({"ok": False, "error": str(e)}, 500)

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


def build_server(port: int = 8765, host: str = "0.0.0.0", dev: bool = False,
                 data_dir: Path | None = None):
    """组装服务器：依赖注入统一 Api 服务。

    唯一的组装根：在这里实例化 ApiService（满足 interfaces.Api 契约）注入到 Handler。
    其余代码一律只依赖 Api 接口（与 CLI 相同）。
    dev=True：开发模式，追加 CORS 头（前端 Vite dev / proxy）。
    data_dir：数据目录（默认仓库根 data/，测试用 test-data/；打包运行时从 bundle 播种）。
    """
    data_dir = ensure_species_seeded(data_dir or DEFAULT_DATA_DIR)
    api = ApiService(data_dir / "species", data_dir / "presets")
    handler = type(
        "InjectedHandler",
        (AssetsLabHandler,),
        {"api": api, "dev_mode": dev},
    )
    return ThreadingHTTPServer((host, port), handler)


def main():
    parser = argparse.ArgumentParser(description="AssetsLab API Server")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--dev", action="store_true",
                        help="开发模式：追加 CORS 头，配合前端 Vite dev (pnpm run dev + proxy) 使用")
    parser.add_argument("--data-dir", default=None,
                        help="数据目录（默认仓库根 data/，测试用 test-data/）")
    args = parser.parse_args()

    if not args.dev and not (WEB_DIST / "index.html").is_file():
        print("Warning: web/dist not found. Run: cd assetslab/web && npm run build", file=sys.stderr)

    data_dir = Path(args.data_dir) if args.data_dir else None
    server = build_server(args.port, args.host, dev=args.dev, data_dir=data_dir)
    mode = "dev" if args.dev else "prod"
    print(f"AssetsLab server [{mode}]: http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
