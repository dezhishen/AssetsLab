from __future__ import annotations

import argparse
import json
import re
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
  <figure><img src=\"character_walk_4way.gif\" alt=\"完整无衣素体四方向行走动画\"><figcaption>完整无衣素体：身体动画与新头部图层合成</figcaption></figure>
  <figure><img src=\"full_walk_master_v1.gif\" alt=\"完整角色行走母版\"><figcaption>完整角色行走母版：暂不接入运行时，仅用于确认动作连续性</figcaption></figure>
  <figure><img src=\"walk_motion_proxy_right_v1.gif\" alt=\"右侧行走动作时序参考\"><figcaption>右侧动作时序参考：用于定义双臂、双腿和过渡帧相位，不作为最终美术素材</figcaption></figure>
  <figure><img src=\"walk_motion_proxy_right_v1_full_loop.gif\" alt=\"右侧完整往返循环参考\"><figcaption>完整往返循环诊断：由半程参考按时间轴反向补齐，仅用于验证摆臂是否闭环</figcaption></figure>
  <figure><img src=\"walk_motion_proxy_right_v1_full_loop_preview.png\" alt=\"右侧完整循环帧序\"><figcaption>完整循环帧序：正向 0 到 7，再反向 6 到 1</figcaption></figure>
  <figure><img src=\"rebuild_body_candidate_front.png\" alt=\"新身体正面基准\"><figcaption>新身体基准图：四方向无衣身体参考</figcaption></figure>
  <figure><img src=\"movement_vertical_body_candidate.gif\" alt=\"latest vertical automatic walk candidate\"><figcaption>Latest vertical walk candidate: automatically captured front/back S/W loop, 8 frames per direction.</figcaption></figure>
  <figure><img src=\"skill_pixel_art_experiment_v1.png\" alt=\"skill pixel art character experiment\"><figcaption>AI pixel-art skill experiment: four-direction clothed character, db16 palette, transparent background.</figcaption></figure>
  <div class=\"grid\">
    <figure><img src=\"body_front.png\" alt=\"正面身体\"><figcaption>身体 0 · 正面</figcaption></figure>
    <figure><img src=\"body_right.png\" alt=\"右侧身体\"><figcaption>身体 1 · 右侧</figcaption></figure>
    <figure><img src=\"body_back.png\" alt=\"背面身体\"><figcaption>身体 2 · 背面</figcaption></figure>
    <figure><img src=\"body_left.png\" alt=\"左侧身体\"><figcaption>身体 3 · 左侧</figcaption></figure>
    <figure><img src=\"character_front.png\" alt=\"正面完整无衣素体\"><figcaption>完整素体 0 · 正面</figcaption></figure>
    <figure><img src=\"character_right.png\" alt=\"右侧完整无衣素体\"><figcaption>完整素体 1 · 右侧</figcaption></figure>
    <figure><img src=\"character_back.png\" alt=\"背面完整无衣素体\"><figcaption>完整素体 2 · 背面</figcaption></figure>
    <figure><img src=\"character_left.png\" alt=\"左侧完整无衣素体\"><figcaption>完整素体 3 · 左侧</figcaption></figure>
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
        for prefix in ("rebuild", "body", "character"):
            shutil.copy2(CURRENT_ASSETS / f"{prefix}_{direction}.png", snapshot_root / f"{prefix}_{direction}.png")
        shutil.copy2(CURRENT_ASSETS / f"rebuild_body_candidate_{direction}.png", snapshot_root / f"rebuild_body_candidate_{direction}.png")
    shutil.copy2(CURRENT_ASSETS / "anchor_debug.png", snapshot_root / "anchor_debug.png")
    for filename in ("body_walk_4way.png", "character_walk_4way.png", "character_walk_4way.gif"):
        shutil.copy2(CURRENT_ASSETS / filename, snapshot_root / filename)
    for filename in ("rgs_walk_reference.gif", "rgs_walk_reference_contact.png", "movement_rgs_reference.gif"):
        source_path = CURRENT_ASSETS / filename
        if source_path.exists():
            shutil.copy2(source_path, snapshot_root / filename)
    for filename in ("movement_vertical_body_candidate.gif",):
        source_path = CURRENT_ASSETS / filename
        if source_path.exists():
            shutil.copy2(source_path, snapshot_root / filename)
    skill_source = ROOT / "prototype" / "assets" / "characters" / "generated" / "skill_pixel_art_experiment_v1" / "turnaround_db16_transparent.png"
    if skill_source.exists():
        shutil.copy2(skill_source, snapshot_root / "skill_pixel_art_experiment_v1.png")
    for filename in ("face_base_walk_4way.png", "face_walk_4way.png", "ears_walk_4way.png", "runtime_manifest.json"):
        shutil.copy2(RUNTIME_ROOT / filename, snapshot_root / filename)

    manifest = {
        "snapshot": snapshot_name,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source": "prototype/assets/characters/rebuild_atlas_v1_runtime/male",
        "directions": ["front", "right", "back", "left"],
        "files": [
            "anchor_debug.png",
            "character_walk_4way.gif",
            "movement_vertical_body_candidate.gif",
            "skill_pixel_art_experiment_v1.png",
            "rgs_walk_reference.gif",
            "rgs_walk_reference_contact.png",
            "movement_rgs_reference.gif",
            "body_walk_4way.png",
            "character_walk_4way.png",
            "rebuild_body_candidate_front.png",
            "rebuild_body_candidate_right.png",
            "rebuild_body_candidate_back.png",
            "rebuild_body_candidate_left.png",
            "rebuild_front.png",
            "rebuild_right.png",
            "rebuild_back.png",
            "rebuild_left.png",
            "body_front.png",
            "body_right.png",
            "body_back.png",
            "body_left.png",
            "character_front.png",
            "character_right.png",
            "character_back.png",
            "character_left.png",
            "face_base_walk_4way.png",
            "face_walk_4way.png",
            "ears_walk_4way.png",
        ],
    }
    (snapshot_root / "snapshot_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    write_snapshot_page(snapshot_root, snapshot_name)
    page_path = snapshot_root / "index.html"
    page = page_path.read_text(encoding="utf-8")
    retired_preview_files = (
        "full_walk_master_v1.gif",
        "walk_motion_proxy_right_v1.gif",
        "walk_motion_proxy_right_v1_full_loop.gif",
        "walk_motion_proxy_right_v1_full_loop_preview.png",
    )
    for retired_file in retired_preview_files:
        page = re.sub(
            r'\s*<figure><img src="' + re.escape(retired_file) + r'".*?</figure>',
            "",
            page,
            flags=re.DOTALL,
        )
    rig_preview = """
  <figure><img src="rgs_walk_reference_contact.png" alt="RGS CC0 八帧行走参考接触表"><figcaption>RGS CC0 开源模块角色：8 帧双腿交替接触表，仅作动作参考</figcaption></figure>
  <figure><img src="rgs_walk_reference.gif" alt="RGS CC0 八帧行走参考"><figcaption>RGS CC0 开源模块角色：手工制作的完整 8 帧行走循环</figcaption></figure>
  <figure><img src="movement_rgs_reference.gif" alt="Godot 实际项目 RGS 行走参考捕获"><figcaption>Godot 隐藏窗口运行时接入：W/A/S/D 流程中的 RGS 行走参考</figcaption></figure>
"""
    page_path.write_text(page.replace("</body>", rig_preview + "</body>"), encoding="utf-8")
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
