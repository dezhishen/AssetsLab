#!/usr/bin/env python3
"""AssetsLab CLI — 与 HTTP API 同级的命令行工具（直接交互，不启动 server）。

CLI 与 HTTP（server.py）共用同一套 Api 接口（assetslab.interfaces.Api，
实现为 assetslab.api.ApiService）→ 两侧行为一致，避免漂移。

用法示例：
  python -m assetslab.cli species list
  python -m assetslab.cli species schema human
  python -m assetslab.cli action list
  python -m assetslab.cli preset new human
  python -m assetslab.cli preset create --json '{"preset_id":"m","species":"human","title":"M","body":{"head_scale":1.2}}'
  python -m assetslab.cli render skeleton human --out skel.png --yaw 45 --body head_scale=1.2,shoulder_width=1.4
  python -m assetslab.cli render motion walk3d --gif --out walk.gif
  python -m assetslab.cli render preset m --action walk3d --out walk.gif
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

_PKG_ROOT = Path(__file__).resolve().parent
_REPO_ROOT = _PKG_ROOT.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from assetslab.api import make_api  # noqa: E402
from assetslab.config import DEFAULT_DATA_DIR  # noqa: E402

_DATA_DIR: Path | None = None  # --data-dir 覆盖（默认仓库根 data/）


def api():
    data_dir = _DATA_DIR or DEFAULT_DATA_DIR
    return make_api(data_dir / "species", data_dir / "presets")


# -- 输出辅助 --


def _json(data) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _save_data_url(out: Path, data_url: str) -> None:
    raw = data_url.split(",", 1)[1] if data_url.startswith("data:") else data_url
    out.write_bytes(base64.b64decode(raw))
    print(f"已写入 {out}")


def _parse_kv(s: str | None) -> dict:
    """解析 'a=1,b=2' → {a:1.0, b:2.0}（体型参数等）。"""
    out: dict = {}
    for pair in (s or "").split(","):
        if "=" not in pair:
            continue
        k, v = pair.split("=", 1)
        try:
            out[k.strip()] = float(v.strip())
        except ValueError:
            out[k.strip()] = v.strip()
    return out


def _load_json_arg(args) -> dict:
    if getattr(args, "json", None):
        return json.loads(args.json)
    if getattr(args, "file", None):
        return json.loads(Path(args.file).read_text(encoding="utf-8"))
    return {}


# -- 命令实现 --


def cmd_species(args) -> None:
    svc = api()
    if args.sub == "list":
        items = svc.species_list()
        if not items:
            print("(无物种)")
            return
        for it in items:
            print(f"  {it['id']:16s} {it.get('title',''):24s} 关节{it.get('joint_count','-')} 动作{len(it.get('actions') or [])}")
    elif args.sub == "show":
        _json(svc.species_get(args.id))
    elif args.sub == "schema":
        _json(svc.species_preset_schema(args.id))
    elif args.sub == "default":
        _json(svc.species_default(args.id))
    elif args.sub == "create":
        data = _load_json_arg(args)
        print("created:", svc.species_create(data))
    elif args.sub == "update":
        print("updated:", svc.species_update(args.id, _load_json_arg(args)))
    elif args.sub == "delete":
        print("deleted:", svc.species_delete(args.id))


def cmd_action(args) -> None:
    svc = api()
    if args.sub == "list":
        for a in svc.actions_list_all():
            print(f"  {a['id']:16s} {a.get('title',''):28s} [{a['species']}] params={list(a.get('params') or {})}")
    elif args.sub == "show":
        _json(svc.action_get(args.species, args.id))
    elif args.sub == "create":
        print("saved:", svc.action_create(args.species, _load_json_arg(args)))
    elif args.sub == "update":
        print("saved:", svc.action_update(args.species, args.id, _load_json_arg(args)))
    elif args.sub == "delete":
        print("deleted:", svc.action_delete(args.species, args.id))


def cmd_preset(args) -> None:
    svc = api()
    if args.sub == "list":
        for p in svc.presets_list():
            print(f"  {p['preset_id']:20s} {p.get('title',''):24s} [{p['species']}]")
    elif args.sub == "new":
        _json(svc.preset_new(args.species))
    elif args.sub == "show":
        _json(svc.preset_get(args.id))
    elif args.sub == "create":
        print("created:", svc.preset_create(_load_json_arg(args)))
    elif args.sub == "update":
        print("updated:", svc.preset_update(args.id, _load_json_arg(args)))
    elif args.sub == "delete":
        print("deleted:", svc.preset_delete(args.id))


def cmd_render(args) -> None:
    svc = api()
    out = Path(args.out)
    if args.mode == "skeleton":
        data_url = svc.render_skeleton3d(
            args.id, yaw=args.yaw, pitch=args.pitch, dist=args.dist, zoom=args.zoom,
            pan_x=args.pan_x, pan_y=args.pan_y, body=_parse_kv(args.body) or None)
        _save_data_url(out, data_url)
    elif args.mode == "motion":
        result = svc.render_motion3d(
            args.id, species=args.species, yaw=args.yaw, pitch=args.pitch, dist=args.dist,
            zoom=args.zoom, pan_x=args.pan_x, pan_y=args.pan_y,
            gif=args.gif, frames=False)
        if "gif" in result:
            _save_data_url(out, result["gif"])
        else:
            _save_data_url(out, result.get("data_url", ""))
    elif args.mode == "preset":
        result = svc.render_preset3d(
            args.id, action_id=args.action, yaw=args.yaw, pitch=args.pitch, dist=args.dist,
            zoom=args.zoom, pan_x=args.pan_x, pan_y=args.pan_y, gif=args.gif)
        if "gif" in result:
            _save_data_url(out, result["gif"])
        else:
            _save_data_url(out, result.get("data_url", ""))
    elif args.mode == "live":
        result = svc.render_preset3d(
            "live", species=args.species, body=_parse_kv(args.body) or None,
            actions=_parse_kv(args.actions) or None, action_id=args.action,
            yaw=args.yaw, pitch=args.pitch, dist=args.dist, zoom=args.zoom,
            pan_x=args.pan_x, pan_y=args.pan_y, gif=args.gif)
        if "gif" in result:
            _save_data_url(out, result["gif"])
        else:
            _save_data_url(out, result.get("data_url", ""))


# -- 参数解析 --

def _add_render_opts(sp) -> None:
    sp.add_argument("--yaw", type=float, default=0)
    sp.add_argument("--pitch", type=float, default=0)
    sp.add_argument("--dist", type=float, default=600)
    sp.add_argument("--zoom", type=float, default=1)
    sp.add_argument("--pan-x", type=float, default=0, dest="pan_x")
    sp.add_argument("--pan-y", type=float, default=0, dest="pan_y")
    sp.add_argument("--out", required=True, help="输出文件（.png / .gif）")
    sp.add_argument("--gif", action="store_true", help="输出 GIF")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="assetslab",
        description="AssetsLab CLI — 与 HTTP API 同级，共用同一套接口（不启动 server）")
    p.add_argument("--data-dir", default=None, help="数据目录（默认仓库根 data/）")
    sub = p.add_subparsers(dest="cmd", required=True)

    # species
    sp = sub.add_parser("species", help="物种管理")
    ssp = sp.add_subparsers(dest="sub", required=True)
    ssp.add_parser("list", help="物种列表")
    s1 = ssp.add_parser("show"); s1.add_argument("id")
    s1 = ssp.add_parser("schema"); s1.add_argument("id", help="预设 schema")
    s1 = ssp.add_parser("default"); s1.add_argument("id")
    c = ssp.add_parser("create"); c.add_argument("--json"); c.add_argument("--file")
    c = ssp.add_parser("update"); c.add_argument("id"); c.add_argument("--json"); c.add_argument("--file")
    d = ssp.add_parser("delete"); d.add_argument("id")

    # action
    ap = sub.add_parser("action", help="动作管理")
    asp = ap.add_subparsers(dest="sub", required=True)
    asp.add_parser("list", help="跨物种动作列表")
    a1 = asp.add_parser("show"); a1.add_argument("species"); a1.add_argument("id")
    a1 = asp.add_parser("create"); a1.add_argument("species"); a1.add_argument("--json"); a1.add_argument("--file")
    a1 = asp.add_parser("update"); a1.add_argument("species"); a1.add_argument("id"); a1.add_argument("--json"); a1.add_argument("--file")
    a1 = asp.add_parser("delete"); a1.add_argument("species"); a1.add_argument("id")

    # preset
    pp = sub.add_parser("preset", help="预设管理（独立入口，调体型 + 动作幅度）")
    psp = pp.add_subparsers(dest="sub", required=True)
    psp.add_parser("list")
    p1 = psp.add_parser("new"); p1.add_argument("species", help="新建空白表单（含 schema）")
    p1 = psp.add_parser("show"); p1.add_argument("id")
    p1 = psp.add_parser("create"); p1.add_argument("--json"); p1.add_argument("--file")
    p1 = psp.add_parser("update"); p1.add_argument("id"); p1.add_argument("--json"); p1.add_argument("--file")
    p1 = psp.add_parser("delete"); p1.add_argument("id")

    # render
    rp = sub.add_parser("render", help="3D 渲染到文件")
    rsub = rp.add_subparsers(dest="mode", required=True)
    r1 = rsub.add_parser("skeleton"); r1.add_argument("id", help="species id")
    r1.add_argument("--body", help="体型参数 a=1,b=2"); _add_render_opts(r1)
    r1 = rsub.add_parser("motion"); r1.add_argument("id", help="action id")
    r1.add_argument("--species", help="限定物种"); _add_render_opts(r1)
    r1 = rsub.add_parser("preset"); r1.add_argument("id", help="preset id")
    r1.add_argument("--action", help="动作 id（省略渲染骨架）"); _add_render_opts(r1)
    r1 = rsub.add_parser("live"); r1.add_argument("--species", required=True)
    r1.add_argument("--body", help="体型参数 a=1,b=2"); r1.add_argument("--actions", help="动作参数 walk3d=intensity=1.2")
    r1.add_argument("--action", help="动作 id"); _add_render_opts(r1)

    return p


def main(argv: list[str] | None = None) -> int:
    global _DATA_DIR
    args = build_parser().parse_args(argv)
    if args.data_dir:
        _DATA_DIR = Path(args.data_dir)
    try:
        if args.cmd == "species":
            cmd_species(args)
        elif args.cmd == "action":
            cmd_action(args)
        elif args.cmd == "preset":
            cmd_preset(args)
        elif args.cmd == "render":
            cmd_render(args)
        else:
            build_parser().print_help()
    except KeyError as e:
        print(f"错误: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001
        print(f"错误: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
