from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

from build_preview_assets import main as build_preview_assets
from build_rebuild_runtime_assets import main as build_rebuild_runtime_assets


ROOT = Path(__file__).resolve().parents[1]
PREVIEW_ROOT = ROOT / "prototype" / "preview"
CURRENT_ASSETS = PREVIEW_ROOT / "assets"
RUNTIME_ROOT = ROOT / "prototype" / "assets" / "characters" / "rebuild_atlas_v1_runtime" / "male"


def safe_name(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in "-_" else "_" for char in value)
    return cleaned.strip("_") or "snapshot"


def write_snapshot_page(snapshot_root: Path, snapshot_name: str) -> None:
    page = f"""<!doctype html>
<html lang=\"zh-CN\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
  <title>AssetsLab Snapshot {snapshot_name}</title>
  <style>
    body {{ margin:0; padding:16px; background:#161827; color:#f2f1ee; font:16px system-ui,sans-serif; }}
    h1 {{ font-size:24px; }}
    p {{ color:#b8bacb; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:14px; }}
    figure {{ margin:0; padding:10px; background:#22253a; border:1px solid #414660; border-radius:12px; }}
    img {{ width:100%; display:block; image-rendering:pixelated; background:#0b0c13; border-radius:8px; }}
    figcaption {{ padding-top:8px; color:#b8bacb; }}
    a {{ color:#8fd3ff; }}
  </style>
</head>
<body>
  <h1>AssetsLab 测试快照</h1>
  <p>快照：<code>{snapshot_name}</code>。此页面只包含该次发布的运行时四方向头部预览。</p>
  <p><a href=\"../../index.html\">返回当前总览</a></p>
  <figure><img src=\"anchor_debug.png\" alt=\"方向轮廓与部件锚点诊断图\"><figcaption>青色：头部轮廓；粉色：脸部锚点；黄色：耳朵锚点</figcaption></figure>
  <div class=\"grid\">
    <figure><img src=\"rebuild_front.png\" alt=\"正脸\"><figcaption>0 · 正脸</figcaption></figure>
    <figure><img src=\"rebuild_right.png\" alt=\"右侧脸\"><figcaption>1 · 右侧脸</figcaption></figure>
    <figure><img src=\"rebuild_back.png\" alt=\"背脸\"><figcaption>2 · 背脸</figcaption></figure>
    <figure><img src=\"rebuild_left.png\" alt=\"左侧脸\"><figcaption>3 · 左侧脸</figcaption></figure>
  </div>
</body>
</html>
"""
    (snapshot_root / "index.html").write_text(page, encoding="utf-8")


def publish_snapshot(name: str | None) -> tuple[str, Path]:
    build_rebuild_runtime_assets()
    build_preview_assets()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    snapshot_name = f"{stamp}-{safe_name(name)}" if name else stamp
    snapshot_root = PREVIEW_ROOT / "snapshots" / snapshot_name
    snapshot_root.mkdir(parents=True, exist_ok=False)

    for direction in ("front", "right", "back", "left"):
        shutil.copy2(CURRENT_ASSETS / f"rebuild_{direction}.png", snapshot_root / f"rebuild_{direction}.png")
    shutil.copy2(CURRENT_ASSETS / "anchor_debug.png", snapshot_root / "anchor_debug.png")
    for filename in ("face_base_walk_4way.png", "face_walk_4way.png", "ears_walk_4way.png", "runtime_manifest.json"):
        shutil.copy2(RUNTIME_ROOT / filename, snapshot_root / filename)

    manifest = {
        "snapshot": snapshot_name,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source": "prototype/assets/characters/rebuild_atlas_v1_runtime/male",
        "directions": ["front", "right", "back", "left"],
        "files": [
            "anchor_debug.png",
            "rebuild_front.png",
            "rebuild_right.png",
            "rebuild_back.png",
            "rebuild_left.png",
            "face_base_walk_4way.png",
            "face_walk_4way.png",
            "ears_walk_4way.png",
        ],
    }
    (snapshot_root / "snapshot_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    write_snapshot_page(snapshot_root, snapshot_name)
    return snapshot_name, snapshot_root


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish a timestamped AssetsLab preview snapshot.")
    parser.add_argument("--name", help="Optional English snapshot label, for example rear_ear_fix")
    args = parser.parse_args()
    snapshot_name, snapshot_root = publish_snapshot(args.name)
    print(f"PREVIEW_SNAPSHOT_PASS name={snapshot_name}")
    print(f"PREVIEW_SNAPSHOT_PATH={snapshot_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
