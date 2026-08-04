from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

# Repository root, set by main(). The workflow console API drives the SAME
# Python SDK (workflow.runner / workflow.store) as the CLI — the Web channel
# and the AI-facing CLI are peer adapters over one engine, they do NOT call
# each other. _SDK holds the lazily imported module handles, set up in main().
REPO_ROOT: Path | None = None
RUN_ROOT: Path | None = None
DEFINITIONS_ROOT: Path | None = None
_SDK: tuple | None = None


class PreviewHandler(SimpleHTTPRequestHandler):
    server_version = "AssetsLabPreview/1.0"

    def log_message(self, format: str, *args: object) -> None:
        # The server is intentionally silent when launched by the hidden
        # preview helper. HTTP errors are still returned to the client.
        return

    def do_GET(self) -> None:
        if self.path.startswith("/api/workflow/"):
            self._workflow_api_get()
            return
        if self.path == "/api/motions" or self.path.startswith("/api/motions/"):
            self._motions_api_get()
            return
        if self.path == "/api/artifacts":
            self._artifacts_api_get()
            return
        if self.path.startswith("/dist/"):
            self._serve_dist_file()
            return
        if self.path.startswith("/run/"):
            self._serve_run_file()
            return
        super().do_GET()

    def do_POST(self) -> None:
        if self.path == "/api/save-pixel-art":
            self._save_pixel_art()
            return
        if self.path.startswith("/api/workflow/"):
            self._workflow_api_post()
            return
        if self.path.startswith("/api/motions/"):
            self._motions_api_post()
            return
        if self.path != "/api/save-calibration":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            schema = payload.get("schema")
            output_name = {
                "component_anchor_calibration_v1": "latest.json",
                "body_anchor_calibration_v1": "body_latest.json",
                "walk_body_component_anchor_calibration_v1": "body_components_latest.json",
                "body_outline_split_v1": "body_outline_split_latest.json",
            }.get(schema)
            if output_name is None:
                raise ValueError("unsupported calibration schema")
            output = Path.cwd() / "calibration" / "latest.json"
            output = output.with_name(output_name)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            body = b'{"saved":true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as error:
            body = json.dumps({"saved": False, "error": str(error)}).encode("utf-8")
            self.send_response(400)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def _save_pixel_art(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if payload.get("schema") != "body_outline_pixel_edit_v1":
                raise ValueError("unsupported pixel edit schema")
            file_name = Path(str(payload.get("file_name", ""))).name
            if not file_name.endswith(".png"):
                raise ValueError("pixel edit output must be a PNG")
            encoded = str(payload.get("png_base64", ""))
            if not encoded:
                raise ValueError("missing PNG data")
            data = base64.b64decode(encoded, validate=True)
            output_dir = (Path.cwd() / "assets").resolve()
            output_dir.mkdir(parents=True, exist_ok=True)
            output = (output_dir / file_name).resolve()
            if output.parent != output_dir:
                raise ValueError("invalid output path")
            output.write_bytes(data)
            body = json.dumps({"saved": True, "file": f"assets/{file_name}"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as error:
            body = json.dumps({"saved": False, "error": str(error)}).encode("utf-8")
            self.send_response(400)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    # ------------------------------------------------------------ workflow --

    def do_DELETE(self) -> None:
        if self.path.startswith("/api/workflow/"):
            self._workflow_api_delete()
            return
        if self.path.startswith("/api/artifacts/"):
            self._artifacts_api_delete()
            return
        self.send_error(404)

    def _workflow_api_delete(self) -> None:
        """DELETE /api/workflow/instances/<id> - remove instance + artifacts."""
        path = self.path[len("/api/workflow/"):].rstrip("/")
        parts = [unquote(p) for p in path.split("/")]
        if len(parts) != 2 or parts[0] != "instances":
            self.send_error(404)
            return
        if REPO_ROOT is None:
            self._send_json({"ok": False, "error": "workflow server not configured"})
            return
        delete_instance = self._sdk()[-2]
        body = self._read_json_body()
        remove_artifacts = bool(body.get("remove_artifacts"))
        try:
            result = delete_instance(REPO_ROOT, RUN_ROOT, parts[1], remove_artifacts)
        except KeyError as error:
            self._send_json({"ok": False, "error": str(error)}, 404)
            return
        self._send_json(self._ok(result))

    def _artifacts_api_delete(self) -> None:
        """DELETE /api/artifacts/<id> - remove only the artifact package."""
        parts = [unquote(p) for p in self.path[len("/api/artifacts/"):].rstrip("/").split("/")]
        if len(parts) != 1 or not parts[0]:
            self.send_error(404)
            return
        if REPO_ROOT is None:
            self._send_json({"ok": False, "error": "workflow server not configured"})
            return
        delete_artifacts = self._sdk()[-1]
        try:
            result = delete_artifacts(REPO_ROOT, parts[0])
        except KeyError as error:
            self._send_json({"ok": False, "error": str(error)}, 404)
            return
        self._send_json(self._ok(result))

    def _send_json(self, payload: object, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _sdk(self) -> tuple:
        """Lazily imported workflow SDK handles (set up in main())."""
        if _SDK is None:
            raise RuntimeError("workflow server not configured (SDK not imported)")
        return _SDK

    def _runner(self, workflow_id: str):
        """Bind a WorkflowRunner to an existing instance, or None."""
        WorkflowRunner, _, _, Store, WorkflowDef, _, _ = self._sdk()
        store = Store(RUN_ROOT, workflow_id)
        if not store.exists():
            return None
        definition = WorkflowDef.load(DEFINITIONS_ROOT / f"{store.load().get('definition_id', 'default')}.json")
        return WorkflowRunner(REPO_ROOT, definition, workflow_id, store)

    def _ok(self, payload: object) -> dict:
        """Wrap an SDK result in the legacy {ok, stdout} envelope the Web UI
        already parses (stdout = JSON payload, exactly like `--json` output)."""
        return {"ok": True, "stdout": json.dumps(payload, ensure_ascii=False)}

    def _err(self, error: Exception) -> dict:
        return {"ok": False, "error": str(error)}

    def _workflow_api_get(self) -> None:
        path = self.path[len("/api/workflow/"):].rstrip("/")
        parts = [unquote(p) for p in path.split("/")]
        if parts == ["list"]:
            if REPO_ROOT is None:
                self._send_json({"ok": False, "error": "workflow server not configured"})
                return
            WorkflowRunner, _, list_instances, _, _, _, _ = self._sdk()
            self._send_json(self._ok(list_instances(REPO_ROOT, RUN_ROOT)))
            return
        if parts == ["templates"]:
            if REPO_ROOT is not None:
                tpl_dir = REPO_ROOT / "workflow" / "templates"
                items = []
                if tpl_dir.is_dir():
                    for path in sorted(tpl_dir.glob("*.json")):
                        try:
                            data = json.loads(path.read_text(encoding="utf-8"))
                        except Exception:
                            continue
                        items.append({
                            "id": data.get("template_id"),
                            "title": data.get("title"),
                            "description": data.get("description", ""),
                            "params": data.get("params", {}),
                        })
                self._send_json({"templates": items})
                return
            self.send_error(404)
            return
        if parts == ["body-templates"]:
            if REPO_ROOT is not None:
                body_dir = REPO_ROOT / "workflow" / "body"
                items = []
                if body_dir.is_dir():
                    for path in sorted(body_dir.glob("*.json")):
                        try:
                            data = json.loads(path.read_text(encoding="utf-8"))
                        except Exception:
                            continue
                        items.append({
                            "id": data.get("body_id"),
                            "title": data.get("title"),
                            "description": data.get("description", ""),
                            "body": data.get("body", {}),
                        })
                self._send_json({"body_templates": items})
                return
            self.send_error(404)
            return
        if parts and parts[0] == "definitions":
            if len(parts) == 1 and DEFINITIONS_ROOT is not None:
                self._send_json({"definitions": sorted(p.stem for p in DEFINITIONS_ROOT.glob("*.json"))})
                return
            if len(parts) == 2 and DEFINITIONS_ROOT is not None:
                # Full definition (incl. per-action tunable params) for the Web console.
                path = DEFINITIONS_ROOT / f"{parts[1]}.json"
                if path.exists():
                    self._send_json(json.loads(path.read_text(encoding="utf-8")))
                    return
            self.send_error(404)
            return
        if len(parts) == 2 and parts[0] == "instances":
            runner = self._runner(parts[1])
            if runner is None:
                self._send_json({"ok": False, "error": f"workflow instance not found: {parts[1]}"}, 404)
                return
            self._send_json(self._ok(runner.status_view()))
            return
        if len(parts) == 3 and parts[0] == "instances" and parts[2] == "artifacts":
            # Exported artifacts for one instance (dist/<workflow_id>/).
            if REPO_ROOT is None:
                self._send_json({"ok": False, "error": "workflow server not configured"})
                return
            try:
                self._send_json({"artifacts": self._artifacts_for(parts[1])})
            except FileNotFoundError as error:
                self._send_json({"ok": False, "error": str(error)}, 404)
            return
        if len(parts) == 3 and parts[0] == "instances" and parts[2] == "next":
            runner = self._runner(parts[1])
            if runner is None:
                self._send_json({"ok": False, "error": f"workflow instance not found: {parts[1]}"}, 404)
                return
            self._send_json(self._ok({"next": runner.next()}))
            return
        self.send_error(404)

    def _workflow_api_post(self) -> None:
        path = self.path[len("/api/workflow/"):].rstrip("/")
        parts = [unquote(p) for p in path.split("/")]
        try:
            body = self._read_json_body()
        except Exception as error:
            self._send_json({"ok": False, "error": str(error)}, 400)
            return
        if REPO_ROOT is None:
            self._send_json({"ok": False, "error": "workflow server not configured"})
            return
        WorkflowRunner, create_instance, _, _, _, _, _ = self._sdk()
        if parts == ["instances"]:
            definition = body.get("definition") or "default"
            workflow_id = body.get("id") or definition
            try:
                result = create_instance(REPO_ROOT, RUN_ROOT, workflow_id, definition,
                                         body.get("template"), body.get("body_template"),
                                         body.get("body") or None,
                                         DEFINITIONS_ROOT,
                                         REPO_ROOT / "workflow" / "templates",
                                         REPO_ROOT / "workflow" / "body")
            except (KeyError, RuntimeError) as error:
                self._send_json(self._err(error))
                return
            self._send_json(self._ok(result))
            return
        if len(parts) == 3 and parts[0] == "instances" and parts[2] == "body":
            # POST /api/workflow/instances/<id>/body  {body: {head_scale: 1.4, ...}}
            runner = self._runner(parts[1])
            if runner is None:
                self._send_json({"ok": False, "error": f"workflow instance not found: {parts[1]}"}, 404)
                return
            try:
                result = runner.set_body(body.get("body") or {})
            except RuntimeError as error:
                self._send_json(self._err(error))
                return
            self._send_json(self._ok({"workflow_id": parts[1], "body": result}))
            return
        if len(parts) == 5 and parts[0] == "instances" and parts[2] == "actions":
            workflow_id, action_id, verb = parts[1], parts[3], parts[4]
            runner = self._runner(workflow_id)
            if runner is None:
                self._send_json({"ok": False, "error": f"workflow instance not found: {workflow_id}"}, 404)
                return
            try:
                if verb != "run":
                    raise RuntimeError(f"unknown action verb: {verb}")
                result = runner.run(action_id, params=body.get("params") or None,
                                    body=body.get("body") or None)
            except (KeyError, RuntimeError) as error:
                self._send_json(self._err(error))
                return
            self._send_json(self._ok(result))
            return
        self.send_error(404)

    # ------------------------------------------------------------ motions --

    def _motions_api_get(self) -> None:
        """GET /api/motions - list available motion presets (pose library)."""
        if REPO_ROOT is None:
            self._send_json({"ok": False, "error": "motion server not configured"})
            return
        motions_dir = REPO_ROOT / "workflow" / "motions"
        items = []
        if motions_dir.is_dir():
            for path in sorted(motions_dir.glob("*.json")):
                if path.name == "base.json":
                    continue
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    continue
                items.append({
                    "id": data.get("motion_id"),
                    "title": data.get("title", data.get("motion_id")),
                    "description": data.get("description", ""),
                    "params": data.get("params", {}),
                    "has_ik": bool(data.get("ik")),
                })
        self._send_json({"motions": items})

    def _motions_api_post(self) -> None:
        """POST /api/motions/{id}/render - render a frame or a full cycle.

        Body: {view, stage, frame_index?, stride?, pelvis_bob?, arm_swing?,
               ik?, blend?, blend_t?} -> returns base64 data URLs.
        """
        parts = [unquote(p) for p in self.path[len("/api/motions/"):].rstrip("/").split("/")]
        if len(parts) != 2 or parts[1] != "render":
            self.send_error(404)
            return
        motion_id = parts[0]
        try:
            body = self._read_json_body()
        except Exception as error:
            self._send_json({"ok": False, "error": str(error)}, 400)
            return
        try:
            result = self._render_motion(motion_id, body)
            self._send_json({"ok": True, **result})
        except Exception as error:
            self._send_json({"ok": False, "error": str(error)}, 500)

    def _render_motion(self, motion_id: str, body: dict) -> dict:
        import base64
        import io

        from PIL import Image

        tools_dir = REPO_ROOT / "workflow" / "tools"
        if str(tools_dir) not in sys.path:
            sys.path.insert(0, str(tools_dir))
        import motion as motion_mod

        motion = motion_mod.load_motion(motion_id)
        view = str(body.get("view", "front"))
        stage = str(body.get("stage", "legs"))
        overrides = {}
        for key in ("stride", "pelvis_bob", "arm_swing"):
            if body.get(key) is not None:
                overrides[key] = float(body[key])
        proportions = {}
        for name in ("arm_length", "leg_length", "torso_length",
                     "shoulder_width", "head_scale", "height"):
            if body.get(name) is not None:
                proportions[name] = float(body[name])
        use_ik = bool(body.get("ik", False))
        blend_id = body.get("blend")
        blend_t = float(body.get("blend_t", 0.0) or 0.0)
        blend = motion_mod.load_motion(blend_id) if blend_id else None

        frame_index = body.get("frame_index")
        if frame_index is not None:
            img = motion_mod.render_frame(motion, view, stage, int(frame_index), overrides or None, use_ik, proportions or None)
            if blend is not None and blend_t > 0.0:
                other = motion_mod.render_frame(blend, view, stage, int(frame_index), overrides or None, use_ik, proportions or None)
                img = Image.blend(img, other, blend_t)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return {"frame": "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()}

        frames = motion_mod.render_motion(motion, view, stage, overrides or None, use_ik, blend, blend_t, proportions or None)
        enlarged = [f.resize((480, 300), Image.Resampling.NEAREST) for f in frames]
        buf = io.BytesIO()
        enlarged[0].save(buf, format="GIF", save_all=True, append_images=enlarged[1:],
                         duration=125, loop=0)
        return {"gif": "data:image/gif;base64," + base64.b64encode(buf.getvalue()).decode()}

    def _serve_run_file(self) -> None:
        if RUN_ROOT is None:
            self.send_error(404)
            return
        # Strip any cache-busting query (?t=...) added by the web UI so the
        # same output file can be re-served without hitting the browser cache.
        path = unquote(urlparse(self.path).path)
        target = (RUN_ROOT / path[len("/run/"):].lstrip("/")).resolve()
        try:
            target.relative_to(RUN_ROOT.resolve())
        except ValueError:
            self.send_error(403)
            return
        if not target.is_file():
            self.send_error(404)
            return
        suffix = target.suffix.lower()
        content_type = {
            ".png": "image/png",
            ".gif": "image/gif",
            ".jpg": "image/jpeg",
            ".json": "application/json; charset=utf-8",
            ".log": "text/plain; charset=utf-8",
            ".txt": "text/plain; charset=utf-8",
        }.get(suffix, "application/octet-stream")
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # ----------------------------------------------------------- artifacts --

    def _artifacts_api_get(self) -> None:
        """GET /api/artifacts - exported artifact packages per instance."""
        if REPO_ROOT is None:
            self._send_json({"ok": False, "error": "workflow server not configured"})
            return
        self._send_json({"artifacts": self._artifacts_for(None)})

    def _artifacts_for(self, workflow_id: str | None) -> list[dict]:
        """Index dist/<workflow_id>/ file trees; workflow_id=None -> all."""
        dist_root = (REPO_ROOT / "dist").resolve()
        ids = [workflow_id] if workflow_id else [d.name for d in sorted(dist_root.iterdir()) if d.is_dir()]
        out: list[dict] = []
        for wid in ids:
            directory = dist_root / wid
            if not directory.is_dir():
                if workflow_id:
                    raise FileNotFoundError(f"no exported artifacts for instance: {wid}")
                continue
            files = []
            for f in sorted(directory.rglob("*")):
                if not f.is_file():
                    continue
                rel = f.relative_to(directory)
                stat = f.stat()
                files.append({
                    "name": f.name,
                    "path": rel.as_posix(),
                    "size": stat.st_size,
                    "mtime": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(timespec="seconds"),
                    "url": f"/dist/{wid}/{rel.as_posix()}",
                })
            out.append({"workflow_id": wid, "files": files})
        return out

    def _serve_dist_file(self) -> None:
        """Serve exported artifacts under /dist/<workflow_id>/...; append
        ?download=1 to force a Content-Disposition attachment."""
        if REPO_ROOT is None:
            self.send_error(404)
            return
        parsed = urlparse(self.path)
        dist_root = (REPO_ROOT / "dist").resolve()
        target = (dist_root / unquote(parsed.path)[len("/dist/"):].lstrip("/")).resolve()
        try:
            target.relative_to(dist_root)
        except ValueError:
            self.send_error(403)
            return
        if not target.is_file():
            self.send_error(404)
            return
        suffix = target.suffix.lower()
        content_type = {
            ".png": "image/png", ".gif": "image/gif", ".jpg": "image/jpeg",
            ".webp": "image/webp", ".json": "application/json; charset=utf-8",
            ".md": "text/markdown; charset=utf-8", ".txt": "text/plain; charset=utf-8",
            ".log": "text/plain; charset=utf-8",
        }.get(suffix, "application/octet-stream")
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        if "download" in parsed.query:
            self.send_header("Content-Disposition", f'attachment; filename="{target.name}"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> int:
    parser = argparse.ArgumentParser(description="AssetsLab LAN preview server with workflow console API")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, help="Repository root (defaults to the parent of --directory).")
    parser.add_argument("--frontend-dir", type=Path,
                        help="Vue build output (workflow/web/dist) served at /. Defaults to workflow/web/dist if present, "
                             "otherwise --directory.")
    parser.add_argument("--webflow-repo", type=str,
                        help="GitHub owner/repo to fetch the webflow dist from (default: inferred from git remote).")
    parser.add_argument("--webflow-version", type=str,
                        help="GitHub Release tag to fetch (default: latest release).")
    parser.add_argument("--webflow-token", type=str,
                        help="GitHub token for private repos / rate limits (env GITHUB_TOKEN also honoured).")
    parser.add_argument("--no-webflow-download", action="store_true",
                        help="Never download the frontend from GitHub; fall back to --directory when dist is missing.")
    args = parser.parse_args()
    global REPO_ROOT, RUN_ROOT, DEFINITIONS_ROOT, _SDK
    REPO_ROOT = (args.repo_root or args.directory.parents[1]).resolve()
    RUN_ROOT = REPO_ROOT / "run"
    DEFINITIONS_ROOT = REPO_ROOT / "workflow" / "definitions"
    # Import the workflow SDK in-process so the Web API is a peer of the CLI
    # (both drive the same engine; neither depends on the other).
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from workflow.model import WorkflowDef  # noqa: E402
    from workflow.runner import WorkflowRunner, create_instance, delete_artifacts, delete_instance, list_instances  # noqa: E402
    from workflow.store import Store  # noqa: E402
    _SDK = (WorkflowRunner, create_instance, list_instances, Store, WorkflowDef, delete_instance, delete_artifacts)
    # Static root: prefer the built Vue frontend (workflow/web/dist); if the
    # local build is missing, try the copy bundled inside a packaged server
    # (sys._MEIPASS), then download from a GitHub Release (based on the build
    # params: --webflow-repo/--webflow-version); otherwise fall back to the
    # --directory static folder (defaults to <repo>/dist).
    frontend_dir = args.frontend_dir or (REPO_ROOT / "workflow" / "web" / "dist")
    usable = frontend_dir.is_dir() and (frontend_dir / "index.html").is_file()
    if not usable:
        bundled = Path(getattr(sys, "_MEIPASS", "")) / "workflow" / "web" / "dist"
        if (bundled / "index.html").is_file():
            frontend_dir = bundled
            usable = True
    if not usable and not args.no_webflow_download:
        token = args.webflow_token or os.environ.get("GITHUB_TOKEN")
        from workflow.webflow import ensure_webflow_dist
        downloaded = ensure_webflow_dist(REPO_ROOT, args.webflow_repo, args.webflow_version, token)
        if downloaded is not None:
            frontend_dir = downloaded
            usable = True
    root = frontend_dir if usable else args.directory.resolve()
    os.chdir(root)
    server = ThreadingHTTPServer(("0.0.0.0", args.port), PreviewHandler)
    server.daemon_threads = True
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
