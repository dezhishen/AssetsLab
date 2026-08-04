#!/usr/bin/env python3
"""生成「人体模特」蒙皮 demo 皮肤。

按 base.json 骨架 rest 姿势 1:1 绘制中性人体几何部件（头/躯干/左右上臂·前臂·
大腿·小腿·脚），输出 dist/mannequin/atlas/<layer>/walk_row{row}_frame0.png，
并生成独立皮肤包 skins/mannequin/（skin.json + <NN>_<layer>_<view>.png + preview/）。

约定：锚点=部件图中心；肢体段从中心沿 +x 水平延伸，由 skin.py 的 rotate_to_joint
绕锚点旋转到 关节->子关节 方向 → rest 时锚点=关节、段两端=起点/终点关节，天然贴合。

用法: python workflow/tools/build_mannequin_skin.py
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

VIEWS = ("front", "side", "back")
VIEW_ROW = {"front": 0, "side": 1, "back": 2}
MARGIN = 8
HEAD_R = 36
NECK_W = 22
TORSO_W_SIDE = 34

SEG_W = {"upper_arm": 13, "forearm": 11, "thigh": 16, "shin": 13, "foot": 12}
SEG_JOINT_R = {"upper_arm": 10, "forearm": 9, "thigh": 11, "shin": 10, "foot": 9}
COLOR_BODY = (200, 210, 220, 255)   # 头/躯干 浅灰蓝
COLOR_SEG = (174, 186, 198, 255)    # 肢体段
COLOR_JOINT = (126, 140, 153, 255)  # 关节球
COLOR_FOOT = (148, 161, 173, 255)

# (zone, layer, 逻辑关节, rotate_child)——逻辑关节用 front 视图的 left_ 系别名，
# 因为 walk 预设的 front 偏移驱动 left_hand/left_foot/…（skin.py VIEW_JOINT 同款）。
# 区域分段：百位 = 身体区域（0头颈 1左臂 2右臂 3躯干 4左腿 5右腿 6脚），
# 十位/个位 = 区域内序号（0 起），每区预留 100 个槽位，方便后续拓展。
ZONES = [
    (0, "head", "head", None),
    (0, "neck", "neck", None),
    (1, "upper_arm_left", "shoulder_left", "left_elbow"),
    (1, "forearm_left", "left_elbow", "left_hand"),
    (2, "upper_arm_right", "shoulder_right", "right_elbow"),
    (2, "forearm_right", "right_elbow", "right_hand"),
    (3, "torso", "pelvis", None),
    (4, "thigh_left", "left_hip", "left_knee"),
    (4, "shin_left", "left_knee", "left_foot"),
    (5, "thigh_right", "right_hip", "right_knee"),
    (5, "shin_right", "right_knee", "right_foot"),
    (6, "foot_left", "left_foot", None),
    (6, "foot_right", "right_foot", None),
]

# 逻辑关节名 -> 各视图实际关节名（side/back 用 front_ 侧为主侧；front 用 left_ 系别名）
# back 视图：手臂用 rear_ 侧（外扩、从背面可见），腿用 front_ 侧（walk back 偏移驱动）。
VIEW_JOINT = {
    ("shoulder_left", "side"): "front_shoulder", ("shoulder_left", "back"): "rear_shoulder_left",
    ("shoulder_right", "side"): "front_shoulder", ("shoulder_right", "back"): "rear_shoulder_right",
    ("left_elbow", "side"): "front_elbow", ("left_elbow", "back"): "rear_elbow_left",
    ("right_elbow", "side"): "front_elbow", ("right_elbow", "back"): "rear_elbow_right",
    ("left_hand", "side"): "front_hand", ("left_hand", "back"): "rear_hand_left",
    ("right_hand", "side"): "front_hand", ("right_hand", "back"): "rear_hand_right",
    ("left_hip", "side"): "front_hip", ("left_hip", "back"): "left_hip",
    ("right_hip", "side"): "front_hip", ("right_hip", "back"): "right_hip",
    ("left_knee", "side"): "front_knee", ("left_knee", "back"): "left_knee",
    ("right_knee", "side"): "front_knee", ("right_knee", "back"): "right_knee",
    ("left_foot", "side"): "front_foot", ("left_foot", "back"): "left_foot",
    ("right_foot", "side"): "front_foot", ("right_foot", "back"): "right_foot",
}


def joint_view(joint: str, view: str) -> str:
    if view == "front":
        return joint
    return VIEW_JOINT.get((joint, view), joint)


def _d(a, b):
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _box(size: int) -> tuple[Image.Image, ImageDraw.ImageDraw, int]:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img), size // 2


def draw_head(radius: int) -> tuple[Image.Image, tuple[int, int]]:
    """纯头（圆）。锚点=圆心（head 关节）。半径随身高/头大小缩放，保持头身比例。"""
    size = 2 * (radius + MARGIN)
    img, d, c = _box(size)
    d.ellipse([c - radius, c - radius, c + radius, c + radius], fill=COLOR_BODY)
    return img, (c, c)


def draw_neck(joints: dict, view: str, head_radius: int) -> tuple[Image.Image, tuple[int, int]]:
    """脖子：head 底 -> neck 关节的垂直段。锚点=图中心（neck 端），向上延伸。
    头随身高缩放后，脖子长度（head 底到 neck）相对头协调，不再显得过长。"""
    head = joints[joint_view("head", view)]
    neck = joints[joint_view("neck", view)]
    h = max(neck[1] - (head[1] + head_radius), 4)  # head 底到 neck 的长度
    size = 2 * (int(math.ceil(h)) + MARGIN)
    img, d, c = _box(size)
    d.rectangle([c - NECK_W // 2, c - h, c + NECK_W // 2, c], fill=COLOR_BODY)
    r = NECK_W // 2
    d.ellipse([c - r, c - r, c + r, c + r], fill=COLOR_JOINT)  # 底部关节球（neck 端）
    return img, (c, c)


def draw_torso(joints: dict, view: str) -> tuple[Image.Image, tuple[int, int]]:
    """躯干（neck->pelvis）。锚点=pelvis（底部中心）。"""
    neck = joints[joint_view("neck", view)]
    pelvis = joints[joint_view("pelvis", view)]
    h = max(pelvis[1] - neck[1], 8)
    if view == "side":
        w = TORSO_W_SIDE
    else:
        left = joints[joint_view("shoulder_left", view)]
        right = joints[joint_view("shoulder_right", view)]
        w = max(right[0] - left[0], 8)
    size = 2 * (int(math.ceil(h)) + MARGIN)
    img, d, c = _box(size)
    d.rectangle([c - w // 2, c - h, c + w // 2, c], fill=COLOR_BODY)
    r = 9
    d.ellipse([c - r, c - r, c + r, c + r], fill=COLOR_JOINT)
    return img, (c, c)


def draw_segment(length: float, seg: str, color: tuple) -> tuple[Image.Image, tuple[int, int]]:
    """肢体段：从锚点（中心）沿 +x 水平延伸 length，两端关节球。
    图尺寸需容纳「段长 + 关节球半径」，否则旋转后球被裁剪。"""
    r = SEG_JOINT_R[seg]
    size = 2 * (int(math.ceil(length)) + r + MARGIN)
    img, d, c = _box(size)
    width = SEG_W[seg]
    d.rectangle([c, c - width // 2, c + int(math.ceil(length)), c + width // 2], fill=color)
    d.ellipse([c - r, c - r, c + r, c + r], fill=COLOR_JOINT)
    d.ellipse([c + int(math.ceil(length)) - r, c - r, c + int(math.ceil(length)) + r, c + r], fill=COLOR_JOINT)
    return img, (c, c)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="生成人体模特皮肤包（可按体型实例化）")
    parser.add_argument("--body", action="append", metavar="NAME=VALUE",
                        help="体型比例覆盖（可重复），如 --body arm_length=1.2 --body leg_length=1.3")
    parser.add_argument("--out", default="mannequin", help="皮肤包名（默认 mannequin）")
    args = parser.parse_args(argv)

    body: dict[str, float] = {}
    for item in args.body or []:
        if "=" in item:
            k, v = item.split("=", 1)
            body[k] = float(v)

    from motion import apply_proportions
    base = json.loads((ROOT / "workflow" / "motions" / "base.json").read_text(encoding="utf-8"))
    views = base["views"]
    skin_root = ROOT / "skins" / args.out
    skin_root.mkdir(parents=True, exist_ok=True)

    # 按体型生成各视图关节（复制避免污染 base.json）——部件段长随体型缩放，蒙皮贴合
    scaled_views: dict[str, dict] = {}
    for view in VIEWS:
        joints = {k: list(v) for k, v in views[view].items()}
        apply_proportions(joints, body or None, view)
        scaled_views[view] = joints

    # 分配区域序号：百位=区域，十位/个位=区域内顺序（每区预留 100 槽）
    seq_of: dict[str, int] = {}
    counters: dict[int, int] = {}
    for zone, layer, _, _ in ZONES:
        seq_of[layer] = zone * 100 + counters.get(zone, 0)
        counters[zone] = counters.get(zone, 0) + 1

    for layer, joint, child in [(l, j, c) for _, l, j, c in ZONES]:
        for view in VIEWS:
            joints = scaled_views[view]
            # 头随身高/头大小缩放，保持头身比例（身高拉长时头也变大，脖子协调）
            head_radius = max(int(HEAD_R * (body.get("height", 1.0) or 1.0) * (body.get("head_scale", 1.0) or 1.0)), 20)
            if layer == "head":
                img, _ = draw_head(head_radius)
            elif layer == "neck":
                img, _ = draw_neck(joints, view, head_radius)
            elif layer == "torso":
                img, _ = draw_torso(joints, view)
            elif layer.startswith("foot"):
                img, _ = draw_segment(20.0, "foot", COLOR_FOOT)
            else:
                a = joints[joint_view(joint, view)]
                b = joints[joint_view(child, view)]
                seg = layer.rsplit("_", 1)[0]
                img, _ = draw_segment(max(_d(a, b), 8.0), seg, COLOR_SEG)
            # 标准命名：<NNN>_<layer>_<view>.png（NNN = 区域分段序号：000头颈/100左臂/200右臂/300躯干/400左腿/500右腿/600脚）
            img.save(skin_root / f"{seq_of[layer]:03d}_{layer}_{view}.png")
            print(f"  {view}/{layer}: {img.size}")

    bindings = {}
    for layer, joint, child in [(l, j, c) for _, l, j, c in ZONES]:
        bindings[layer] = {"joint": joint, "rotate": False}
        if child:
            bindings[layer]["rotate_child"] = child
    body_desc = f"，体型 {body or '标准 1.0'}" if body else ""
    skin = {
        "skin_id": args.out,
        "schema": "assetslab_skin_v1",
        "layout": "pack",
        "description": f"人体模特皮肤（{args.out}）：按 base.json 骨架 1:1 绘制的中性人体几何部件{body_desc}。"
                       "锚点=部件图中心（精确=关节），肢体段按骨骼段方向旋转（rotate_child），rest 天然贴合。"
                       "皮肤包独立于制品；序号按区域分段（3 位）：000头颈/100左臂/200右臂/300躯干/400左腿/500右腿/600脚。",
        "views": list(VIEWS),
        "coordinates": "skeleton",
        "atlas_dir": f"skins/{args.out}",
        "layers": [{"name": l, "zone": z, "order": seq_of[l] % 100} for z, l, _, _ in ZONES],
        "bindings": bindings,
        "anchors": {},
    }
    (skin_root / "skin.json").write_text(json.dumps(skin, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"MANNEQUIN_SKIN_OK zones={len({z for z, *_ in ZONES})} layers={len(ZONES)} -> {skin_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
