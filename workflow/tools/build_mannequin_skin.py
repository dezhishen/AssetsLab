#!/usr/bin/env python3
"""生成「人体模特」蒙皮 demo 皮肤。

按 base.json 骨架 rest 姿势 1:1 绘制中性人体几何部件（头/躯干/左右上臂·前臂·
大腿·小腿·脚），输出 dist/mannequin/atlas/<layer>/walk_row{row}_frame0.png，
并生成 workflow/skins/mannequin.json（coordinates=skeleton）。

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
NECK_H = 52
NECK_W = 22
TORSO_W_SIDE = 34

SEG_W = {"upper_arm": 13, "forearm": 11, "thigh": 16, "shin": 13, "foot": 12}
SEG_JOINT_R = {"upper_arm": 10, "forearm": 9, "thigh": 11, "shin": 10, "foot": 9}
COLOR_BODY = (200, 210, 220, 255)   # 头/躯干 浅灰蓝
COLOR_SEG = (174, 186, 198, 255)    # 肢体段
COLOR_JOINT = (126, 140, 153, 255)  # 关节球
COLOR_FOOT = (148, 161, 173, 255)

# (layer, 逻辑关节, rotate_child) —— 逻辑关节用 front 视图的 left_ 系别名，
# 因为 walk 预设的 front 偏移驱动 left_hand/left_foot/…（skin.py VIEW_JOINT 同款）。
LAYERS = [
    ("head", "head", None),
    ("torso", "pelvis", None),
    ("upper_arm_left", "shoulder_left", "left_elbow"),
    ("upper_arm_right", "shoulder_right", "right_elbow"),
    ("forearm_left", "left_elbow", "left_hand"),
    ("forearm_right", "right_elbow", "right_hand"),
    ("thigh_left", "left_hip", "left_knee"),
    ("thigh_right", "right_hip", "right_knee"),
    ("shin_left", "left_knee", "left_foot"),
    ("shin_right", "right_knee", "right_foot"),
    ("foot_left", "left_foot", None),
    ("foot_right", "right_foot", None),
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


def draw_head() -> tuple[Image.Image, tuple[int, int]]:
    """头（圆）+ 脖子。锚点=圆心（head 关节）。"""
    size = 2 * (HEAD_R + NECK_H + MARGIN)
    img, d, c = _box(size)
    d.ellipse([c - HEAD_R, c - HEAD_R, c + HEAD_R, c + HEAD_R], fill=COLOR_BODY)
    d.rectangle([c - NECK_W // 2, c + HEAD_R, c + NECK_W // 2, c + HEAD_R + NECK_H], fill=COLOR_BODY)
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
    size = 2 * (h + MARGIN)
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


def main() -> int:
    base = json.loads((ROOT / "workflow" / "motions" / "base.json").read_text(encoding="utf-8"))
    views = base["views"]
    skin_root = ROOT / "skins" / "mannequin"
    skin_root.mkdir(parents=True, exist_ok=True)

    for idx, (layer, joint, child) in enumerate(LAYERS, start=1):
        for view in VIEWS:
            joints = views[view]
            if layer == "head":
                img, _ = draw_head()
            elif layer == "torso":
                img, _ = draw_torso(joints, view)
            elif layer.startswith("foot"):
                img, _ = draw_segment(20.0, "foot", COLOR_FOOT)
            else:
                a = joints[joint_view(joint, view)]
                b = joints[joint_view(child, view)]
                seg = layer.rsplit("_", 1)[0]
                img, _ = draw_segment(max(_d(a, b), 8.0), seg, COLOR_SEG)
            # 标准命名：<NN>_<layer>_<view>.png（NN = 绘制顺序的数字序号前缀）
            img.save(skin_root / f"{idx:02d}_{layer}_{view}.png")
            print(f"  {view}/{layer}: {img.size}")

    bindings = {}
    for layer, joint, child in LAYERS:
        bindings[layer] = {"joint": joint, "rotate": False}
        if child:
            bindings[layer]["rotate_child"] = child
    skin = {
        "skin_id": "mannequin",
        "schema": "assetslab_skin_v1",
        "layout": "pack",
        "description": "通用人体模特皮肤：按 base.json 骨架 1:1 绘制的中性人体几何部件。"
                       "锚点=部件图中心（精确=关节），肢体段按骨骼段方向旋转（rotate_child），rest 天然贴合。"
                       "皮肤包独立于制品：skins/mannequin/（skin.json + <NN>_<layer>_<view>.png）。",
        "views": list(VIEWS),
        "coordinates": "skeleton",
        "atlas_dir": "skins/mannequin",
        "layers": [{"name": l, "order": i} for i, (l, _, _) in enumerate(LAYERS, 1)],
        "bindings": bindings,
        "anchors": {},
    }
    (skin_root / "skin.json").write_text(json.dumps(skin, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"MANNEQUIN_SKIN_OK layers={len(LAYERS)} views={len(VIEWS)} -> {skin_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
