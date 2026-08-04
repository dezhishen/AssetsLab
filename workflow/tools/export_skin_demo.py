#!/usr/bin/env python3
"""把程序化皮肤「烘焙」成 Godot demo 兼容的制品包 dist/<name>/。

皮肤是「部件 + 骨骼」的几何蒙皮（渲染时按骨架关节实时合成）；Godot demo
（player.gd）消费的是**预烘焙分层帧** atlas + runtime_manifest.json。本脚本
在导出时逐帧渲染皮肤，裁成 64x64 cell 的 7 层帧（demo 层），并生成 manifest，
使皮肤能直接跑进 demo：

  - 方向: front→front, right→side, back→back, left→side 水平镜像
  - 层映射（皮肤 13 层 → demo 7 层）:
      feet       → {foot_left, foot_right}
      lower_body → {thigh_left, shin_left, thigh_right, shin_right}
      arms       → {upper_arm_*, forearm_*}（左右）
      torso      → {torso, neck}
      head_base  → {head}
      ear / face → 空层（皮肤无耳/脸）
  - 每方向用该方向整帧 bbox 求统一变换（裁剪 + 缩放 + 底部对齐），
    所有层共享同一变换，叠加后 = 完整角色 → head_anchor_offsets 全 0、layer_y=0

用法:
  python workflow/tools/export_skin_demo.py --skin orc [--out orc]
输出:
  dist/<out>/atlas/<layer>/walk_row{0-3}_frame{0-7}.png
  dist/<out>/runtime_manifest.json
  dist/<out>/character_walk_4way.gif
  dist/<out>/README.md
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from skin import (
    SKINS_ROOT, load_motion, load_skin, resolve_atlas, skin_frame, skin_layout,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "dist"

CELL = 64
ROWS = 4
FRAMES = 8
MARGIN = 4
DIRECTIONS = ["front", "right", "back", "left"]
DEMO_LAYERS = ("feet", "lower_body", "arms", "torso", "head_base", "ear", "face")

# demo 层 -> 皮肤层集合（皮肤包层名；缺失的层自动跳过）
LAYER_MAP: dict[str, set[str]] = {
    "feet": {"foot_left", "foot_right"},
    "lower_body": {"thigh_left", "shin_left", "thigh_right", "shin_right"},
    "arms": {"upper_arm_left", "forearm_left", "upper_arm_right", "forearm_right"},
    "torso": {"torso", "neck"},
    "head_base": {"head"},
    "ear": set(),
    "face": set(),
}

# demo 方向 -> (皮肤视图, 是否水平镜像)
DIR_VIEW = {
    "front": ("front", False),
    "right": ("side", False),
    "back": ("back", False),
    "left": ("side", True),
}


def fit_transform(full: Image.Image) -> tuple[float, int, int]:
    """整帧 -> (scale, 目标宽, 目标高)：裁剪 bbox 后按比例缩放，适配 cell。"""
    bbox = full.getchannel("A").getbbox()
    if not bbox:
        return 1.0, 0, 0
    l, t, r, b = bbox
    w, h = r - l, b - t
    avail = CELL - 2 * MARGIN
    scale = min(avail / w, avail / h) if w and h else 1.0
    scale = min(scale, 1.0)  # 不放大（960x600 已是足量像素，只会缩小）
    return scale, round(w * scale), round(h * scale)


def layer_cell(piece: Image.Image, bbox: tuple[int, int, int, int],
               scale: float, tw: int, th: int, mirror: bool) -> Image.Image:
    """把某层渲染图裁剪到整帧 bbox、缩放、贴到 cell 底部居中。"""
    crop = piece.crop(bbox)
    if tw and th and crop.width and crop.height:
        crop = crop.resize((tw, th), Image.Resampling.NEAREST)
    cell = Image.new("RGBA", (CELL, CELL), (0, 0, 0, 0))
    x = (CELL - crop.width) // 2
    y = CELL - crop.height - MARGIN  # 底部对齐（脚贴地），留 MARGIN 底边距
    cell.alpha_composite(crop, (x, y))
    if mirror:
        cell = cell.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    return cell


def write_manifest(dist: Path, name: str, skin_id: str, body: dict | None,
                   files: list[str], runtime_params: dict | None = None) -> None:
    offsets = {d: [0, 0] for d in DIRECTIONS}  # 层已在 cell 内对齐，无需头偏移
    manifest = {
        "schema": "assetslab_artifact_v1",
        "workflow_id": name,
        "generator": "workflow/tools/export_skin_demo.py",
        "skin_id": skin_id,
        "body": body or None,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cell_size": [CELL, CELL],
        "directions": DIRECTIONS,
        "frames_per_direction": FRAMES,
        "layer_order": list(DEMO_LAYERS),
        "head_anchor_offsets": offsets,
        "runtime_params": runtime_params or {},
        "atlas_dir": "atlas",
        "preview_gif": "character_walk_4way.gif",
        "files": sorted(files),
    }
    (dist / "runtime_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_readme(dist: Path, name: str, skin_id: str) -> None:
    readme = f"""# AssetsLab Artifact · {name}

由 `workflow/tools/export_skin_demo.py` 从皮肤包 `skins/{skin_id}` 烘焙生成
（皮肤 + 骨骼蒙皮 → 预烘焙分层帧制品）。

## Contents

- `atlas/` — 7 层 4×8 帧: `feet`, `lower_body`, `arms`, `torso`, `head_base`,
  `ear`, `face`（ear/face 为空层）。
- `runtime_manifest.json` — directions, layer order, `head_anchor_offsets`（全 0）。
- `character_walk_4way.gif` — 四向行走预览。

## Run in the Godot demo

```bash
godot --path prototype -- --artifacts dist/{name}
```

皮肤源可替换：重新生成皮肤后用本脚本重新烘焙即可换角色。
"""
    (dist / "README.md").write_text(readme, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="把皮肤烘焙成 Godot demo 制品包 dist/<name>/")
    parser.add_argument("--skin", required=True, help="皮肤包 id（skins/<id>/）")
    parser.add_argument("--out", default=None, help="制品名（默认 = skin id）")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="dist 根目录（默认 <repo>/dist）")
    parser.add_argument("--motion", default="walk", help="动画预设（默认 walk）")
    parser.add_argument("--move-speed", type=float, default=180.0)
    parser.add_argument("--walk-fps", type=float, default=8.0)
    args = parser.parse_args()

    skin_id = args.skin
    name = args.out or skin_id
    dist = args.output / name
    atlas = dist / "atlas"
    if dist.exists():
        shutil.rmtree(dist)

    skin = load_skin(skin_id)
    atlas_dir = resolve_atlas(skin, None)
    layout = skin_layout(skin, atlas_dir)
    proportions = skin.get("body") or None
    motion = load_motion(args.motion)
    frame_count = int(motion.get("frame_count", FRAMES))

    # 校验层名：把 LAYER_MAP 中不存在的皮肤层剔除（空层 ear/face 保留）
    have = set(skin_layers := [l["name"] if isinstance(l, dict) else l
                               for l in skin.get("layers", [])])

    files: list[str] = []
    gif_frames: list[Image.Image] = []
    for dir_index, direction in enumerate(DIRECTIONS):
        view, mirror = DIR_VIEW[direction]
        # 该方向整帧 bbox -> 统一变换（所有层共享）
        full = skin_frame(motion, view, "arms", 0, None, proportions,
                          skin, atlas_dir, layout)
        bbox = full.getchannel("A").getbbox()
        if not bbox:
            raise SystemExit(f"[x] {skin_id}/{direction}: 整帧为空（无内容可烘焙）")
        scale, tw, th = fit_transform(full)
        for frame in range(frame_count):
            for layer in DEMO_LAYERS:
                src_layers = LAYER_MAP[layer] & have
                piece = skin_frame(motion, view, "arms", frame, None, proportions,
                                   skin, atlas_dir, layout, only_layers=sorted(src_layers))
                cell = layer_cell(piece, bbox, scale, tw, th, mirror)
                dst_dir = atlas / layer
                dst_dir.mkdir(parents=True, exist_ok=True)
                path = dst_dir / f"walk_row{dir_index}_frame{frame}.png"
                cell.save(path)
                files.append(f"atlas/{layer}/walk_row{dir_index}_frame{frame}.png")
            # 预览帧：整帧应用同一变换
            preview = layer_cell(full if frame == 0 else
                                 skin_frame(motion, view, "arms", frame, None,
                                            proportions, skin, atlas_dir, layout),
                                 bbox, scale, tw, th, mirror)
            gif_frames.append(preview)

    # 四向行走预览 GIF
    enlarged = [f.resize((256, 256), Image.Resampling.NEAREST) for f in gif_frames]
    gif_path = dist / "character_walk_4way.gif"
    enlarged[0].save(gif_path, save_all=True, append_images=enlarged[1:],
                     duration=100, loop=0, disposal=2)
    files.append("character_walk_4way.gif")

    # layer_y 需与 main.tscn 里 body 层 sprite 的位置一致（(0,-26)），否则 head
    # sprite 被放到 (0,layer_y) 而 body 在 (0,-26)，脑袋会脱离躯干上移。
    runtime_params = {"move_speed": args.move_speed, "walk_fps": args.walk_fps, "layer_y": -26.0}
    write_manifest(dist, name, skin_id, skin.get("body"), files, runtime_params)
    write_readme(dist, name, skin_id)
    print(f"SKIN_DEMO_EXPORT_PASS skin={skin_id} -> {dist.resolve()}")
    print(f"ARTIFACT_PREVIEW={gif_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
