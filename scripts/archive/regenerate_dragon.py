#!/usr/bin/env python3
"""重建三头飞龙（three_head_dragon）骨骼、预设与 3D 动作。

参考成熟幻想游戏（三头龙 / 希德龙）的设定整理：
  - 三首分明：左/中/右三个头 + 各自颈链（脖子从颈根分叉上扬），头间距拉开；
  - 四肢规整：前肢 = shoulder→elbow→wrist→paw（足掌），后肢 = hip→knee→ankle→foot，
    去除冗余的 heel/toe/talon 贴地杂点；
  - 双翼大而展开：chest→wing_shoulder→wing_elbow→wing_wrist→wing_tip；
  - 长尾：pelvis→tail_base→tail_mid1→tail_mid2→tail_tip；
  - 动作：收翅蹲伏待机 idle / 飞行 fly(flight=true) / 喷火 fire_breath。

用法：python scripts/regenerate_dragon.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from assetslab.species import SpeciesService

CX = 480.0
FLOOR_Y = 470.0
HEAD_R = 20.0

SPECIES_ROOT = ROOT / "assetslab" / "species"
PRESETS_ROOT = ROOT / "assetslab" / "presets"
SP_DIR = SPECIES_ROOT / "three_head_dragon"


def _r(v: float) -> float:
    return round(v, 1)


# =========================================================================
# 1. 3D 关节坐标：按解剖比例推导（头高 T 为单位），不写死像素。
#    改姿态/比例只需调 DRAGON_SPEC 里几个比值，再重跑脚本即可。
# =========================================================================
DRAGON_SPEC = {
    "head_radius": 18.0,
    "back_height": 3.7,     # 背线离地高度（头数）→ 背接近水平
    "torso_len": 7.0,       # 躯干长度 chest→pelvis（头数）→ 背长拉开，前后肢不再挤在胸上
    "belly_sag": 0.15,      # 腹部低于背线（头数）
    "leg_len": 3.7,         # 四肢长度（肩/髋→地，头数）→ 前后肢等长
    "fore_back": 0.22,      # 前肢略后倾（x 头数）
    "hind_fwd": 0.18,       # 后肢略前伸（x 头数）
    "shoulder_w": 0.9,      # 肩宽半宽（头数）
    "hip_w": 0.8,           # 髋宽半宽（头数）
    "neck_base_h": 0.4,     # 颈根高出背线（头数）
    "neck_len": 2.5,        # 颈长（颈根→头，头数）
    "head_fan": 1.5,        # 三头扇形半宽（头数）
    "wing_span": 6.4,       # 翼展半宽（头数）
    "wing_rise": 0.9,       # 翼上翘（头数）
    "wing_sweep": 1.4,      # 翼后掠（z 头数）→ 侧视有纵深
    "tail_len": 5.0,        # 尾长（头数）
}


def gen_joints3d(spec: dict) -> dict[str, list[float]]:
    """由比例推导全部关节 [x,y,z]（头高 T 为单位；y 下正，x 左右，z 前后）。

    躯干沿 x-z 斜向拉开：x 投影保证正面视图看得到长背，z 投影保证侧面/3D
    视图也有背长纵深——前后肢不再挤在胸口、侧面也不塌成一条竖线。
    """
    T = 2.0 * spec["head_radius"]
    def Y(r: float) -> float:
        return FLOOR_Y - r * T          # r 头数离地高度 → y
    back_y = Y(spec["back_height"])
    half = spec["torso_len"] * T / 2.0  # 躯干半长（沿体轴）
    tx = 0.78 * half                     # 体轴在 x（左右）投影 → 正面可见背长
    tz = 0.62 * half                     # 体轴在 z（纵深）投影 → 侧面可见背长
    leg = spec["leg_len"] * T           # 四肢长
    chest_x = CX - tx                    # 前胸（体轴前端，靠左）
    pelvis_x = CX + tx                   # 骨盆（体轴后端，靠右）
    chest_z = tz                         # 前胸略靠前
    pelvis_z = -tz                       # 骨盆略靠后
    J: dict[str, list[float]] = {}
    def P(n, x, y, z):
        J[n] = [_r(x), _r(y), _r(z)]
    # 左右侧：left→s=-1（x 减），right→s=+1（x 加）
    def lr(base: float, off: float, s: float) -> float:
        return base + s * off

    # --- 躯干（背线水平：chest 与 pelvis 等高；背长沿体轴拉开） ---
    P("chest", chest_x, back_y, chest_z)
    P("abdomen", CX, back_y + spec["belly_sag"] * T, 0)
    P("pelvis", pelvis_x, back_y, pelvis_z)

    # --- 三颈 + 三首（颈根在前胸，颈上扬扇形，头横排分清） ---
    nb_y = back_y - spec["neck_base_h"] * T
    mid_y = nb_y - spec["neck_len"] * T * 0.55
    top_y = nb_y - spec["neck_len"] * T
    fan = spec["head_fan"] * T
    P("neck_base", chest_x, nb_y, chest_z + 0.25 * T)
    P("neck_mid", chest_x, mid_y, chest_z + 0.45 * T)
    P("head", chest_x, top_y, chest_z + 0.6 * T)
    P("jaw", chest_x, top_y + 0.32 * T, chest_z + 0.9 * T)
    for side, s in (("left", -1), ("right", 1)):
        P(f"neck_base_{side}", lr(chest_x, 0.55 * T, s), nb_y, chest_z + 0.15 * T)
        P(f"neck_mid_{side}", lr(chest_x, fan * 0.6, s), mid_y, chest_z + 0.35 * T)
        P(f"head_{side}", lr(chest_x, fan, s), top_y + 0.1 * T, chest_z + 0.5 * T)
        P(f"jaw_{side}", lr(chest_x, fan, s), top_y + 0.42 * T, chest_z + 0.8 * T)

    # --- 前肢（肩在胸前下方，足略前伸） ---
    for side, s in (("left", -1), ("right", 1)):
        sx = lr(chest_x, spec["shoulder_w"] * T, s)
        bx = lr(sx, spec["fore_back"] * T, s)
        P(f"shoulder_{side}", sx, back_y, chest_z * 0.55)
        P(f"elbow_{side}", bx, back_y + leg * 0.45, chest_z * 0.4)
        P(f"wrist_{side}", bx, back_y + leg * 0.78, chest_z * 0.3)
        P(f"paw_{side}", bx, FLOOR_Y, chest_z * 0.3)

    # --- 后肢（髋在骨盆下方，足略后收） ---
    for side, s in (("left", -1), ("right", 1)):
        hx = lr(pelvis_x, spec["hip_w"] * T, s)
        bx = lr(hx, spec["hind_fwd"] * T, s)
        P(f"hip_{side}", hx, back_y, pelvis_z * 0.55)
        P(f"knee_{side}", bx, back_y + leg * 0.5, pelvis_z * 0.4)
        P(f"ankle_{side}", bx, back_y + leg * 0.8, pelvis_z * 0.3)
        P(f"foot_{side}", bx, FLOOR_Y, pelvis_z * 0.3)

    # --- 双翼（附着肩部上方，向两侧展开、上翘、后掠） ---
    for side, s in (("left", -1), ("right", 1)):
        wx = lr(chest_x, spec["shoulder_w"] * T, s)
        P(f"wing_shoulder_{side}", wx, back_y - 0.3 * T, chest_z * 0.5)
        P(f"wing_elbow_{side}", lr(wx, spec["wing_span"] * T * 0.3, s), back_y - (0.3 + spec["wing_rise"] * 0.5) * T, chest_z * 0.5 - spec["wing_sweep"] * T * 0.4)
        P(f"wing_wrist_{side}", lr(wx, spec["wing_span"] * T * 0.62, s), back_y - (0.3 + spec["wing_rise"] * 0.8) * T, chest_z * 0.5 - spec["wing_sweep"] * T * 0.7)
        P(f"wing_tip_{side}", lr(wx, spec["wing_span"] * T, s), back_y - (0.3 + spec["wing_rise"]) * T, chest_z * 0.5 - spec["wing_sweep"] * T)

    # --- 长尾（骨盆向后下方，随体轴向后延伸） ---
    P("tail_base", pelvis_x, back_y + 0.12 * T, pelvis_z - 0.5 * T)
    P("tail_mid1", pelvis_x + 0.25 * T, back_y + 0.5 * T, pelvis_z - spec["tail_len"] * T * 0.32)
    P("tail_mid2", pelvis_x + 0.4 * T, back_y + 0.85 * T, pelvis_z - spec["tail_len"] * T * 0.62)
    P("tail_tip", pelvis_x + 0.5 * T, back_y + 1.15 * T, pelvis_z - spec["tail_len"] * T)
    return J


def positions3d() -> dict[str, list[float]]:
    return gen_joints3d(DRAGON_SPEC)


# =========================================================================
# 2. 骨架拓扑
# =========================================================================
BONES_3D = [
    ["jaw", "head"], ["head", "neck_mid"], ["neck_mid", "neck_base"],
    ["jaw_left", "head_left"], ["head_left", "neck_mid_left"], ["neck_mid_left", "neck_base_left"],
    ["jaw_right", "head_right"], ["head_right", "neck_mid_right"], ["neck_mid_right", "neck_base_right"],
    ["neck_base", "neck_base_left"], ["neck_base", "neck_base_right"],
    ["neck_base", "chest"], ["chest", "abdomen"], ["abdomen", "pelvis"],
    ["chest", "shoulder_left"], ["shoulder_left", "elbow_left"], ["elbow_left", "wrist_left"], ["wrist_left", "paw_left"],
    ["chest", "shoulder_right"], ["shoulder_right", "elbow_right"], ["elbow_right", "wrist_right"], ["wrist_right", "paw_right"],
    ["pelvis", "hip_left"], ["hip_left", "knee_left"], ["knee_left", "ankle_left"], ["ankle_left", "foot_left"],
    ["pelvis", "hip_right"], ["hip_right", "knee_right"], ["knee_right", "ankle_right"], ["ankle_right", "foot_right"],
    ["chest", "wing_shoulder_left"], ["wing_shoulder_left", "wing_elbow_left"], ["wing_elbow_left", "wing_wrist_left"], ["wing_wrist_left", "wing_tip_left"],
    ["chest", "wing_shoulder_right"], ["wing_shoulder_right", "wing_elbow_right"], ["wing_elbow_right", "wing_wrist_right"], ["wing_wrist_right", "wing_tip_right"],
    ["pelvis", "tail_base"], ["tail_base", "tail_mid1"], ["tail_mid1", "tail_mid2"], ["tail_mid2", "tail_tip"],
]

CENTERLINE = ["jaw", "head", "neck_mid", "neck_base", "chest", "abdomen", "pelvis",
              "tail_base", "tail_mid1", "tail_mid2", "tail_tip"]

CHAINS = {
    "spine": CENTERLINE,
    "neck_left": ["neck_base_left", "neck_mid_left", "head_left", "jaw_left"],
    "neck_right": ["neck_base_right", "neck_mid_right", "head_right", "jaw_right"],
    "foreleg_left": ["shoulder_left", "elbow_left", "wrist_left", "paw_left"],
    "foreleg_right": ["shoulder_right", "elbow_right", "wrist_right", "paw_right"],
    "hindleg_left": ["hip_left", "knee_left", "ankle_left", "foot_left"],
    "hindleg_right": ["hip_right", "knee_right", "ankle_right", "foot_right"],
    "wing_left": ["wing_shoulder_left", "wing_elbow_left", "wing_wrist_left", "wing_tip_left"],
    "wing_right": ["wing_shoulder_right", "wing_elbow_right", "wing_wrist_right", "wing_tip_right"],
}

PARAM_CHAINS = {
    "head_cluster": {"joints": ["head", "head_left", "head_right", "jaw", "jaw_left", "jaw_right"],
                     "param": "head_scale", "anchor": "bottom"},
    "neck_cluster": {"joints": ["neck_mid", "neck_mid_left", "neck_mid_right", "head", "head_left", "head_right",
                                "neck_base_left", "neck_base_right"],
                     "param": "neck_length", "anchor": "neck_base"},
    "torso": {"joints": ["neck_base", "chest", "abdomen", "pelvis"], "param": "torso_length", "anchor": "pelvis"},
    "shoulder_girdle": {"joints": ["shoulder_left", "shoulder_right", "wing_shoulder_left", "wing_shoulder_right"],
                        "param": "shoulder_width", "anchor": "center"},
    "hip_girdle": {"joints": ["hip_left", "hip_right"], "param": "hip_width", "anchor": "center"},
    "foreleg_left": {"joints": ["elbow_left", "wrist_left", "paw_left"], "param": "foreleg_length", "anchor": "shoulder_left"},
    "foreleg_right": {"joints": ["elbow_right", "wrist_right", "paw_right"], "param": "foreleg_length", "anchor": "shoulder_right"},
    "hindleg_left": {"joints": ["knee_left", "ankle_left", "foot_left"], "param": "hindleg_length", "anchor": "hip_left"},
    "hindleg_right": {"joints": ["knee_right", "ankle_right", "foot_right"], "param": "hindleg_length", "anchor": "hip_right"},
    "wing_left": {"joints": ["wing_elbow_left", "wing_wrist_left", "wing_tip_left"], "param": "wing_span", "anchor": "wing_shoulder_left"},
    "wing_right": {"joints": ["wing_elbow_right", "wing_wrist_right", "wing_tip_right"], "param": "wing_span", "anchor": "wing_shoulder_right"},
    "tail": {"joints": ["tail_base", "tail_mid1", "tail_mid2", "tail_tip"], "param": "tail_length", "anchor": "pelvis"},
}

# 左右镜像对（用于验证 symmetry3d）
SYM_PAIRS = []
for part in ("neck_base", "neck_mid", "head", "jaw",
             "shoulder", "elbow", "wrist", "paw",
             "hip", "knee", "ankle", "foot",
             "wing_shoulder", "wing_elbow", "wing_wrist", "wing_tip"):
    SYM_PAIRS.append([f"{part}_left", f"{part}_right"])


def skeleton() -> dict:
    joints = {
        "centerline": CENTERLINE,
        "left_head": ["neck_base_left", "neck_mid_left", "head_left", "jaw_left"],
        "right_head": ["neck_base_right", "neck_mid_right", "head_right", "jaw_right"],
        "left_foreleg": CHAINS["foreleg_left"],
        "right_foreleg": CHAINS["foreleg_right"],
        "left_hindleg": CHAINS["hindleg_left"],
        "right_hindleg": CHAINS["hindleg_right"],
        "left_wing": CHAINS["wing_left"],
        "right_wing": CHAINS["wing_right"],
        "aliases": {"head_center": "head", "jaw_center": "jaw",
                    "front_paw_left": "paw_left", "front_paw_right": "paw_right",
                    "rear_foot_left": "foot_left", "rear_foot_right": "foot_right"},
    }
    # 2D 视图（front/side/back）命名映射
    def side_map(j):
        if j.endswith("_left"):
            return "front_" + j[:-5]
        if j.endswith("_right"):
            return "rear_" + j[:-6]
        return j
    def back_map(j):
        if j.endswith("_left") or j.endswith("_right"):
            return "rear_" + j
        return j
    def bones_for(mapper, mirror_x):
        out, seen = [], set()
        for a, b in BONES_3D:
            na, nb = mapper(a), mapper(b)
            key = (na, nb) if na < nb else (nb, na)
            if key in seen:
                continue
            seen.add(key)
            out.append([na, nb])
        return out

    return {
        "species_id": "three_head_dragon",
        "schema": "assetslab_species_v1",
        "title": "三头飞龙",
        "description": "三头飞龙骨骼拓扑：三首分明（左/中/右）、四肢规整、双翼展开、长尾后扬。",
        "param_chains": PARAM_CHAINS,
        "joints": joints,
        "bones": {
            "front": BONES_3D,
            "side": bones_for(side_map, False),
            "back": bones_for(back_map, True),
        },
        "bones_3d": BONES_3D,
        "chains": CHAINS,
        "torso_joints": CENTERLINE,
        "upper_joints": ["jaw", "head", "jaw_left", "head_left", "jaw_right", "head_right",
                         "neck_mid", "neck_base", "neck_base_left", "neck_mid_left",
                         "neck_base_right", "neck_mid_right", "chest",
                         "shoulder_left", "elbow_left", "wrist_left", "paw_left",
                         "shoulder_right", "elbow_right", "wrist_right", "paw_right",
                         "wing_shoulder_left", "wing_elbow_left", "wing_wrist_left", "wing_tip_left",
                         "wing_shoulder_right", "wing_elbow_right", "wing_wrist_right", "wing_tip_right"],
        "constraints": {
            "schema": "assetslab_constraints_v1",
            "description": "三头飞龙物理/解剖约束：足掌/脚掌刚性跟随；左右镜像对称。",
            "rigid_chains": {"chains": [
                {"driver": "wrist_left", "follow": ["paw_left"]},
                {"driver": "wrist_right", "follow": ["paw_right"]},
                {"driver": "ankle_left", "follow": ["foot_left"]},
                {"driver": "ankle_right", "follow": ["foot_right"]},
            ]},
            "symmetry3d": {"pairs": SYM_PAIRS, "tolerance": 14.0},
            "coordination": {"axis": "z", "pairs": [
                ["ankle_left", "wing_wrist_right"],
                ["ankle_right", "wing_wrist_left"],
            ]},
        },
    }


# =========================================================================
# 3. 预设（positions_3d + 2D 派生）
# =========================================================================
def derive_views2d(j3: dict) -> dict:
    front, side, back = {}, {}, {}
    def sm(j):
        if j.endswith("_left"):
            return "front_" + j[:-5]
        if j.endswith("_right"):
            return "rear_" + j[:-6]
        return j
    for j, (x, y, z) in j3.items():
        front[j] = [_r(x), _r(y)]
        side[sm(j)] = [_r(CX + z), _r(y)]
        back["rear_" + j if (j.endswith("_left") or j.endswith("_right")) else j] = [_r(2 * CX - x), _r(y)]
    return {"front": front, "side": side, "back": back}


def preset(j3: dict) -> dict:
    params = {
        "head_scale": {"default": 1.0, "min": 0.6, "max": 1.6, "step": 0.05, "label": "头部体积"},
        "neck_length": {"default": 1.0, "min": 0.6, "max": 1.6, "step": 0.05, "label": "颈部长度"},
        "torso_length": {"default": 1.0, "min": 0.6, "max": 1.6, "step": 0.05, "label": "躯干长度"},
        "shoulder_width": {"default": 1.0, "min": 0.6, "max": 1.6, "step": 0.05, "label": "肩带宽度"},
        "hip_width": {"default": 1.0, "min": 0.6, "max": 1.6, "step": 0.05, "label": "髋带宽度"},
        "foreleg_length": {"default": 1.0, "min": 0.6, "max": 1.6, "step": 0.05, "label": "前肢长度"},
        "hindleg_length": {"default": 1.0, "min": 0.6, "max": 1.6, "step": 0.05, "label": "后肢长度"},
        "wing_span": {"default": 1.0, "min": 0.6, "max": 1.8, "step": 0.05, "label": "翼展"},
        "tail_length": {"default": 1.0, "min": 0.6, "max": 1.8, "step": 0.05, "label": "尾长"},
    }
    return {
        "preset_id": "three_head_dragon_default",
        "schema": "assetslab_preset_v3",
        "title": "三头飞龙·默认",
        "description": "三头飞龙基础预设：三首分明、四肢规整、双翼展开、长尾后扬。",
        "species": "three_head_dragon",
        "head_radius": HEAD_R,
        "canvas": {"width": 960, "height": 600, "floor_y": FLOOR_Y},
        "params": params,
        "body": {k: 1.0 for k in params},
        "positions_3d": j3,
        "positions": derive_views2d(j3),
    }


# =========================================================================
# 4. 3D 动作
# =========================================================================
def ik_chains() -> dict:
    return {"chains": [
        {"root": "shoulder_left", "mid": "elbow_left", "tip": "wrist_left", "pole": [0.0, 0.0, 1.0]},
        {"root": "shoulder_right", "mid": "elbow_right", "tip": "wrist_right", "pole": [0.0, 0.0, 1.0]},
        {"root": "hip_left", "mid": "knee_left", "tip": "ankle_left", "pole": [0.0, 0.0, 1.0]},
        {"root": "hip_right", "mid": "knee_right", "tip": "ankle_right", "pole": [0.0, 0.0, 1.0]},
    ]}


def _fold_offsets(j3: dict, spec: dict, side: str) -> dict:
    """收翅偏移：由 spec 推导——翼沿体侧下折贴腹（段长靠翼 IK 保持，不是向内缩短）。"""
    T = 2.0 * spec["head_radius"]
    s = -1 if side == "left" else 1
    tuck = -s                       # 向体内收方向：left→+x, right→-x
    ws = j3[f"wing_shoulder_{side}"]
    out: dict[str, dict[str, float]] = {}
    for jn, (xh, yh, zh) in {
        "wing_elbow": (1.0, 0.5, -0.35),
        "wing_wrist": (1.7, 1.2, -0.55),
        "wing_tip": (2.1, 2.0, -0.8),
    }.items():
        base = j3[f"{jn}_{side}"]
        tg = [ws[0] + xh * T * tuck, ws[1] + yh * T, ws[2] + zh * T]
        out[f"{jn}_{side}"] = {"x": _r(tg[0] - base[0]), "y": _r(tg[1] - base[1]), "z": _r(tg[2] - base[2])}
    return out


def action_idle(j3: dict, spec: dict) -> dict:
    fold: dict[str, dict[str, float]] = {}
    for side in ("left", "right"):
        fold.update(_fold_offsets(j3, spec, side))
    def fe(joint: str, axis: str) -> dict:
        return {"mul": [{"param": "wing_fold"}, fold[joint][axis]]}
    wing_ik: list[dict] = []
    for side in ("left", "right"):
        wing_ik += [
            {"root": f"wing_shoulder_{side}", "mid": f"wing_elbow_{side}", "tip": f"wing_wrist_{side}", "pole": [0.0, 1.0, -0.4]},
            {"root": f"wing_elbow_{side}", "mid": f"wing_wrist_{side}", "tip": f"wing_tip_{side}", "pole": [0.0, 1.0, -0.4]},
        ]
    return {
        "schema": "assetslab_motion3d_v1",
        "motion_id": "idle_crouch_folded_wings3d",
        "title": "Idle 3D — 收翅蹲伏待机",
        "description": "三头飞龙蹲伏待机：低重心、翼沿体侧下折贴腹（保持翼长）、三首轻摆、尾巴缓摆、呼吸起伏。",
        "species": "three_head_dragon",
        "frame_count": 8,
        "params": {
            "intensity": {"default": 1.0, "min": 0.0, "max": 1.6, "label": "力度"},
            "crouch": {"default": 1.0, "min": 0.0, "max": 2.0, "label": "蹲伏"},
            "wing_fold": {"default": 1.0, "min": 0.0, "max": 2.0, "label": "收翅"},
            "breath": {"default": 1.0, "min": 0.0, "max": 2.0, "label": "呼吸"},
            "head_sway": {"default": 1.0, "min": 0.0, "max": 2.0, "label": "头颈摆动"},
            "tail_sway": {"default": 1.0, "min": 0.0, "max": 2.0, "label": "尾摆"},
        },
        "signals": {
            "phase": {"phase": True},
            "breath": {"mul": [{"sin": {"phase": True}}, {"param": "breath"}, {"param": "intensity"}]},
            "head": {"mul": [{"sin": {"phase": True}}, {"param": "head_sway"}, {"param": "intensity"}]},
            "head_r": {"neg": {"signal": "head"}},
            "tail": {"mul": [{"sin": {"add": [{"phase": True}, 1.2]}}, {"param": "tail_sway"}, {"param": "intensity"}]},
        },
        "root3d": {
            "y": {"mul": [{"param": "crouch"}, 16.0]},
            "z": {"mul": [{"signal": "breath"}, -2.0]},
        },
        "offsets3d": {
            "chest": {"y": {"mul": [{"signal": "breath"}, -2.5]}},
            "neck_mid": {"y": {"mul": [{"signal": "breath"}, -1.4]}},
            "head": {"z": {"mul": [{"signal": "head"}, 4.0]}},
            "head_left": {"z": {"mul": [{"signal": "head_r"}, 3.5]}, "x": {"mul": [{"signal": "head_r"}, 2.0]}},
            "head_right": {"z": {"mul": [{"signal": "head"}, 3.5]}, "x": {"mul": [{"signal": "head"}, 2.0]}},
            "tail_base": {"z": {"mul": [{"signal": "tail"}, -6.0]}},
            "tail_mid1": {"z": {"mul": [{"signal": "tail"}, -10.0]}},
            "tail_mid2": {"z": {"mul": [{"signal": "tail"}, -14.0]}},
            "tail_tip": {"z": {"mul": [{"signal": "tail"}, -18.0]}},
            # 收翅：翼沿体侧下折贴腹（段长由翼 IK 保持，不缩短）
            "wing_elbow_left": {"x": fe("wing_elbow_left", "x"), "y": fe("wing_elbow_left", "y"), "z": fe("wing_elbow_left", "z")},
            "wing_wrist_left": {"x": fe("wing_wrist_left", "x"), "y": fe("wing_wrist_left", "y"), "z": fe("wing_wrist_left", "z")},
            "wing_tip_left": {"x": fe("wing_tip_left", "x"), "y": fe("wing_tip_left", "y"), "z": fe("wing_tip_left", "z")},
            "wing_elbow_right": {"x": fe("wing_elbow_right", "x"), "y": fe("wing_elbow_right", "y"), "z": fe("wing_elbow_right", "z")},
            "wing_wrist_right": {"x": fe("wing_wrist_right", "x"), "y": fe("wing_wrist_right", "y"), "z": fe("wing_wrist_right", "z")},
            "wing_tip_right": {"x": fe("wing_tip_right", "x"), "y": fe("wing_tip_right", "y"), "z": fe("wing_tip_right", "z")},
        },
        "ik3d": {"chains": ik_chains()["chains"] + wing_ik},
    }


def action_fly() -> dict:
    return {
        "schema": "assetslab_motion3d_v1",
        "motion_id": "fly3d",
        "title": "Fly 3D — 振翼飞行",
        "description": "三头飞龙空中巡航：双翼大幅振拍、躯干起伏、三首稳定、尾巴平衡、后肢垂悬。",
        "species": "three_head_dragon",
        "frame_count": 8,
        "flight": True,
        "params": {
            "intensity": {"default": 1.0, "min": 0.0, "max": 1.8, "label": "力度"},
            "flap": {"default": 1.0, "min": 0.0, "max": 2.0, "label": "振翼"},
            "lift": {"default": 1.0, "min": 0.0, "max": 2.0, "label": "升力"},
            "forward": {"default": 1.0, "min": 0.0, "max": 2.0, "label": "前冲"},
            "head_stabilize": {"default": 1.0, "min": 0.0, "max": 2.0, "label": "头部稳定"},
            "tail_balance": {"default": 1.0, "min": 0.0, "max": 2.0, "label": "尾平衡"},
        },
        "signals": {
            "phase": {"phase": True},
            "flap": {"mul": [{"sin": {"phase": True}}, {"param": "flap"}, {"param": "intensity"}]},
            "lift": {"mul": [{"cos": {"phase": True}}, {"param": "lift"}, {"param": "intensity"}]},
            "tail": {"mul": [{"sin": {"add": [{"phase": True}, 1.8]}}, {"param": "tail_balance"}, {"param": "intensity"}]},
            "head": {"mul": [{"sin": {"add": [{"phase": True}, 3.14]}}, {"param": "head_stabilize"}, {"param": "intensity"}]},
        },
        "root3d": {
            "y": {"mul": [{"signal": "lift"}, -9.0]},
            "z": {"mul": [{"param": "forward"}, -12.0]},
        },
        "offsets3d": {
            "wing_elbow_left": {"y": {"mul": [{"signal": "flap"}, 28.0]}, "z": {"mul": [{"signal": "flap"}, -18.0]}},
            "wing_wrist_left": {"y": {"mul": [{"signal": "flap"}, 44.0]}, "z": {"mul": [{"signal": "flap"}, -28.0]}},
            "wing_tip_left": {"y": {"mul": [{"signal": "flap"}, 58.0]}, "z": {"mul": [{"signal": "flap"}, -36.0]}},
            "wing_elbow_right": {"y": {"mul": [{"signal": "flap"}, 28.0]}, "z": {"mul": [{"signal": "flap"}, -18.0]}},
            "wing_wrist_right": {"y": {"mul": [{"signal": "flap"}, 44.0]}, "z": {"mul": [{"signal": "flap"}, -28.0]}},
            "wing_tip_right": {"y": {"mul": [{"signal": "flap"}, 58.0]}, "z": {"mul": [{"signal": "flap"}, -36.0]}},
            # 后肢垂悬（轻微前后摆）
            "ankle_left": {"z": {"mul": [{"signal": "tail"}, 6.0]}},
            "ankle_right": {"z": {"mul": [{"signal": "tail"}, 6.0]}},
            "head": {"z": {"mul": [{"signal": "head"}, 4.0]}},
            "head_left": {"z": {"mul": [{"signal": "head"}, 3.0]}},
            "head_right": {"z": {"mul": [{"signal": "head"}, 3.0]}},
            "tail_base": {"z": {"mul": [{"signal": "tail"}, -8.0]}},
            "tail_mid1": {"z": {"mul": [{"signal": "tail"}, -13.0]}},
            "tail_mid2": {"z": {"mul": [{"signal": "tail"}, -18.0]}},
            "tail_tip": {"z": {"mul": [{"signal": "tail"}, -24.0]}},
        },
        "ik3d": ik_chains(),
    }


def action_fire() -> dict:
    return {
        "schema": "assetslab_motion3d_v1",
        "motion_id": "fire_breath3d",
        "title": "Fire Breath 3D — 三首喷焰",
        "description": "三头飞龙喷火：三颈前探、下颌张开、躯干前压、翼部张力支撑、尾巴反向平衡。",
        "species": "three_head_dragon",
        "frame_count": 8,
        "params": {
            "intensity": {"default": 1.0, "min": 0.0, "max": 1.8, "label": "力度"},
            "charge": {"default": 1.0, "min": 0.0, "max": 2.0, "label": "蓄力"},
            "neck_thrust": {"default": 1.0, "min": 0.0, "max": 2.0, "label": "颈部前探"},
            "jaw_open": {"default": 1.0, "min": 0.0, "max": 2.0, "label": "张口"},
            "wing_brace": {"default": 1.0, "min": 0.0, "max": 2.0, "label": "翼部支撑"},
            "tail_counter": {"default": 1.0, "min": 0.0, "max": 2.0, "label": "尾部反向平衡"},
        },
        "signals": {
            "phase": {"phase": True},
            "burst": {"mul": [{"table": [0.0, 0.3, 0.9, 1.0, 0.7, 0.3, 0.1, 0.0]}, {"param": "charge"}, {"param": "intensity"}]},
            "brace": {"mul": [{"table": [0.2, 0.4, 0.8, 1.0, 0.9, 0.5, 0.3, 0.2]}, {"param": "wing_brace"}, {"param": "intensity"}]},
            "counter": {"mul": [{"table": [0.0, 0.2, 0.5, 0.8, 0.8, 0.5, 0.2, 0.0]}, {"param": "tail_counter"}, {"param": "intensity"}]},
        },
        "root3d": {
            "z": {"mul": [{"signal": "burst"}, 14.0]},
            "y": {"mul": [{"signal": "burst"}, 3.0]},
        },
        "offsets3d": {
            "chest": {"z": {"mul": [{"signal": "burst"}, 10.0]}},
            "neck_mid": {"z": {"mul": [{"signal": "burst"}, 12.0]}},
            "neck_base_left": {"z": {"mul": [{"signal": "burst"}, 8.0]}, "x": {"mul": [{"signal": "burst"}, -4.0]}},
            "neck_mid_left": {"z": {"mul": [{"signal": "burst"}, 14.0]}, "x": {"mul": [{"signal": "burst"}, -6.0]}},
            "head_left": {"z": {"mul": [{"signal": "burst"}, 18.0]}, "x": {"mul": [{"signal": "burst"}, -7.0]}},
            "jaw_left": {"y": {"mul": [{"param": "jaw_open"}, 8.0]}, "z": {"mul": [{"signal": "burst"}, 10.0]}},
            "head": {"z": {"mul": [{"signal": "burst"}, 20.0]}},
            "jaw": {"y": {"mul": [{"param": "jaw_open"}, 9.0]}, "z": {"mul": [{"signal": "burst"}, 12.0]}},
            "neck_base_right": {"z": {"mul": [{"signal": "burst"}, 8.0]}, "x": {"mul": [{"signal": "burst"}, 4.0]}},
            "neck_mid_right": {"z": {"mul": [{"signal": "burst"}, 14.0]}, "x": {"mul": [{"signal": "burst"}, 6.0]}},
            "head_right": {"z": {"mul": [{"signal": "burst"}, 18.0]}, "x": {"mul": [{"signal": "burst"}, 7.0]}},
            "jaw_right": {"y": {"mul": [{"param": "jaw_open"}, 8.0]}, "z": {"mul": [{"signal": "burst"}, 10.0]}},
            "wing_elbow_left": {"y": {"mul": [{"signal": "brace"}, -10.0]}, "z": {"mul": [{"signal": "brace"}, -8.0]}},
            "wing_wrist_left": {"y": {"mul": [{"signal": "brace"}, -14.0]}, "z": {"mul": [{"signal": "brace"}, -12.0]}},
            "wing_tip_left": {"y": {"mul": [{"signal": "brace"}, -18.0]}, "z": {"mul": [{"signal": "brace"}, -18.0]}},
            "wing_elbow_right": {"y": {"mul": [{"signal": "brace"}, -10.0]}, "z": {"mul": [{"signal": "brace"}, -8.0]}},
            "wing_wrist_right": {"y": {"mul": [{"signal": "brace"}, -14.0]}, "z": {"mul": [{"signal": "brace"}, -12.0]}},
            "wing_tip_right": {"y": {"mul": [{"signal": "brace"}, -18.0]}, "z": {"mul": [{"signal": "brace"}, -18.0]}},
            "tail_base": {"z": {"mul": [{"signal": "counter"}, -10.0]}},
            "tail_mid1": {"z": {"mul": [{"signal": "counter"}, -15.0]}},
            "tail_mid2": {"z": {"mul": [{"signal": "counter"}, -20.0]}},
            "tail_tip": {"z": {"mul": [{"signal": "counter"}, -26.0]}},
        },
        "ik3d": ik_chains(),
    }


# =========================================================================
# 主流程
# =========================================================================
def main() -> None:
    j3 = positions3d()
    sk = skeleton()
    (SP_DIR / "skeleton.json").write_text(json.dumps(sk, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"skeleton.json: {len(j3)} joints, {len(sk['bones_3d'])} bones_3d")

    # 预设 schema 随骨架自动派生
    svc = SpeciesService(SPECIES_ROOT)
    svc.update("three_head_dragon", sk)

    p = preset(j3)
    (PRESETS_ROOT / "three_head_dragon" / "three_head_dragon_default.json").write_text(
        json.dumps(p, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"preset: positions_3d={len(p['positions_3d'])}, views={ {k: len(v) for k, v in p['positions'].items()} }")

    adir = SP_DIR / "actions3d"
    for fn, a in [("idle_crouch_folded_wings3d.json", action_idle(j3, DRAGON_SPEC)),
                  ("fly3d.json", action_fly()),
                  ("fire_breath3d.json", action_fire())]:
        (adir / fn).write_text(json.dumps(a, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"action: {a['motion_id']} (frame_count={a['frame_count']})")


if __name__ == "__main__":
    main()
