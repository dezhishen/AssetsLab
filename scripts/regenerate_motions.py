#!/usr/bin/env python3
"""Regenerate species/human/actions/{idle,jump,run,walk}.json

Redesigns the four locomotion actions based on mature animation practice:

  * walk — contact / down / pass / up cycle: leg stride + foot lift (IK-linked
    knee bend), pelvis bob + pelvic sway, torso counter-rotation, shoulder-led
    arm swing, forward lean.
  * run  — adds a flight phase (both feet airborne), high knee drive, heel kick
    up behind, bigger body travel and forward lean.
  * jump — anticipation crouch -> launch -> airborne tuck -> landing absorb.
  * idle — breathing idle: rib/chest expansion, shoulder rise, pelvis bob,
    subtle weight shift and arm sway.

View joint-name conventions (from species/human/skeleton.json bones):
  front:  hip_left / knee_left / foot_left ; elbow_left / wrist_left / palm_left / finger_left
  side:   rear_* 与 front_*（近/远侧腿臂）
  back:   rear_*_left / rear_*_right（背面只画 rear 腿臂链；躯干用 rib_upper_* / sternum / pelvis）

The JSON uses *canonical* joint names only; the motion engine syncs aliases
(left_foot <-> foot_left) automatically.  Each motion carries an orthogonal
parameter set (each slider controls one limb characteristic) plus an
`intensity` master that scales everything in coordination.

Run:  python scripts/regenerate_motions.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTIONS = ROOT / "assetslab/species/human/actions"
SKELETON = ROOT / "assetslab/species/human/skeleton.json"

# ---------------------------------------------------------------- helpers


def P(name):
    return {"param": name}


def S(name):
    return {"signal": name}


def PH():
    return {"phase": True}


def sin(e):
    return {"sin": e}


def cos(e):
    return {"cos": e}


def neg(e):
    return {"neg": e}


def rect(e):
    return {"rect": e}


def mul(*e):
    return {"mul": list(e)}


def add(*e):
    return {"add": list(e)}


def table(*vals):
    return {"table": list(vals)}


def xy(x=None, y=None):
    out = {}
    if x is not None:
        out["x"] = x
    if y is not None:
        out["y"] = y
    return out


def arm_chain(*names, x_expr=None, y_expr=None, elbow_x=None, elbow_y=None):
    """Build rigid arm-chain offsets.

    The elbow bends (offset < hand), while wrist/palm/finger move together as a
    rigid unit so the forearm never stretches. ``names`` are the joints in
    chain order, e.g. ("elbow_left", "wrist_left", "palm_left", "finger_left").
    """
    out = {}
    elbow = names[0]
    if elbow_x is not None or elbow_y is not None:
        out[elbow] = xy(x=elbow_x, y=elbow_y if elbow_y is not None else y_expr)
    elif x_expr is not None or y_expr is not None:
        out[elbow] = xy(x=x_expr, y=y_expr)
    for j in names[1:]:
        out[j] = xy(x=x_expr, y=y_expr)
    return out


def _elbow(el_x, el_y):
    """Return (elbow_x_expr, elbow_y_expr); accepts a plain expr or (x, y) pair."""
    if el_x is None and el_y is None:
        return None, None
    if isinstance(el_x, tuple) or (isinstance(el_x, list)):
        return el_x[0], el_x[1]
    return el_x, el_y


# front-view arm chains (left uses el_l, right uses el_r so each side can have
# its own phase / amplitude — sharing one elbow expr for both sides tore the
# forearm because left/right swing in opposite phase)


# 手臂：只偏移 WRIST（前臂末端 = 手目标）；肘由手臂 IK 解出；palm/finger 由引擎
# 的 _HAND_GROUPS 从 wrist 刚性传播。这样手臂真正绕肩旋转、肘自然弯曲，不撕裂。
def front_hands(left_x, left_y, right_x, right_y):
    return {
        "wrist_left": xy(x=left_x, y=left_y),
        "wrist_right": xy(x=right_x, y=right_y),
    }


def side_hands(front_x, front_y, rear_x, rear_y):
    return {
        "front_wrist": xy(x=front_x, y=front_y),
        "rear_wrist": xy(x=rear_x, y=rear_y),
    }


def back_hands(left_x, left_y, right_x, right_y):
    return {
        "rear_wrist_left": xy(x=left_x, y=left_y),
        "rear_wrist_right": xy(x=right_x, y=right_y),
    }


def knob(default, lo, hi, step, label, desc):
    return {"default": default, "min": lo, "max": hi, "step": step,
            "label": label, "desc": desc}


def motion(motion_id, title, description, params, signals, offsets,
           root=None, selectors=None, ik=None, frame_count=8, species="human"):
    data = {
        "schema": "assetslab_motion_v1",
        "motion_id": motion_id,
        "title": title,
        "description": description,
        "frame_count": frame_count,
        "params": params,
        "signals": signals,
    }
    if root is not None:
        data["root"] = root
    data["offsets"] = offsets
    if selectors is not None:
        data["selectors"] = selectors
    if ik is not None:
        data["ik"] = ik
    data["species"] = species
    return data


def write(motion_id, data):
    path = ACTIONS / f"{motion_id}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)}")


# ------------------------------------------------------------- validation


def validate(data):
    """Warn if an offset references a joint unknown to the skeleton bones."""
    skel = json.loads(SKELETON.read_text(encoding="utf-8"))
    known = set()
    for v, pairs in skel.get("bones", {}).items():
        for a, b in pairs:
            known.add(a)
            known.add(b)
    aliases = skel.get("joints", {}).get("aliases", {}) or {}
    bad = []
    for view, stages in data["offsets"].items():
        for stage, joints in stages.items():
            for j in joints:
                if j not in known and j not in aliases and j not in ("pelvis",):
                    bad.append(f"{view}/{stage}:{j}")
    return bad


# -------------------------------------------------------------- ik groups


def ik_groups():
    """IK 组。腿：末端 = ankle（真小腿段）；臂：末端 = wrist（真前臂段）。
    foot/heel/toe 与 palm/finger 分别由 ankle/wrist 刚性传播。"""
    return {
        "front": {
            "legs": {
                "left": {"hip": "hip_left", "knee": "knee_left", "foot": "ankle_left"},
                "right": {"hip": "hip_right", "knee": "knee_right", "foot": "ankle_right"},
            },
            "arms": {
                "left": {"shoulder": "shoulder_left", "elbow": "elbow_left", "hand": "wrist_left"},
                "right": {"shoulder": "shoulder_right", "elbow": "elbow_right", "hand": "wrist_right"},
            },
        },
        "side": {
            "legs": {
                "rear": {"hip": "rear_hip", "knee": "rear_knee", "foot": "rear_ankle"},
                "front": {"hip": "front_hip", "knee": "front_knee", "foot": "front_ankle"},
            },
            "arms": {
                "front": {"shoulder": "front_shoulder", "elbow": "front_elbow", "hand": "front_wrist"},
                "rear": {"shoulder": "rear_shoulder", "elbow": "rear_elbow", "hand": "rear_wrist"},
            },
        },
        "back": {
            "legs": {
                "left": {"hip": "rear_hip_left", "knee": "rear_knee_left", "foot": "rear_ankle_left"},
                "right": {"hip": "rear_hip_right", "knee": "rear_knee_right", "foot": "rear_ankle_right"},
            },
            "arms": {
                "left": {"shoulder": "rear_shoulder_left", "elbow": "rear_elbow_left", "hand": "rear_wrist_left"},
                "right": {"shoulder": "rear_shoulder_right", "elbow": "rear_elbow_right", "hand": "rear_wrist_right"},
            },
        },
    }


def walk_selectors():
    return {
        "front_leg": table("left", "left", "left", "left",
                           "right", "right", "right", "right"),
        "foreground_leg": table("front", "front", "front", "front",
                                "rear", "rear", "rear", "rear"),
        "foreground": table("left", "left", "left", "left",
                            "right", "right", "right", "right"),
    }


# ------------------------------------------------------------------ walk


def build_walk():
    params = {
        "intensity": knob(1.0, 0.0, 1.5, 0.05, "力度协调",
                          "主参数：协调步幅/起伏/摆臂等整体强度"),
        "stride": knob(1.0, 0.0, 2.0, 0.05, "步幅",
                       "腿部前后跨步幅度（水平）"),
        "step_height": knob(1.0, 0.0, 2.0, 0.05, "步高",
                            "摆动脚离地高度（IK 联动自然屈膝）"),
        "pelvis_bob": knob(1.0, 0.0, 2.0, 0.05, "骨盆起伏",
                           "身体上下起伏幅度（过位最高、支撑最低）"),
        "pelvic_sway": knob(1.0, 0.0, 2.0, 0.05, "骨盆侧摆",
                            "骨盆左右/前后摆动，躯干反向形成扭转"),
        "torso_lean": knob(1.0, 0.0, 2.0, 0.05, "前倾",
                           "上身前倾幅度（行走动态平衡）"),
        "arm_swing": knob(1.0, 0.0, 2.0, 0.05, "摆臂",
                          "摆臂幅度（肩部带动，与腿反向）"),
    }
    signals = {
        "phase": PH(),
        # 基础步幅（左/后腿水平）；右/前腿取反
        "swing": mul(sin(PH()), P("stride"), P("intensity")),
        "swing_r": neg(S("swing")),
        # 抬脚窗口：sin² 包络（过零斜率 0 → 平滑启动/停止，避免抬脚瞬间突跳）
        "lift": mul(rect(sin(PH())), sin(PH()), sin(PH())),
        "lift_r": mul(rect(neg(sin(PH()))), neg(sin(PH())), neg(sin(PH()))),
        # 身体起伏（正=下，负=上）：对称 table——双腿并拢(过位 f2/f6)时最高，
        # 张开(支撑 f0/f4)时最低。左右步态完全对称（f2=f6），帧间≤7px 平滑。
        "bob": mul(table(3.0, 0.0, -7.0, 0.0, 3.0, 0.0, -7.0, 0.0),
                   P("pelvis_bob"), P("intensity")),
        # 骨盆侧摆 / 旋转
        "sway": mul(sin(PH()), P("pelvic_sway"), P("intensity")),
        # 前倾（常量）
        "lean": mul(P("torso_lean"), P("intensity")),
        # 摆臂（与同侧腿反向）
        "arm": mul(sin(PH()), P("arm_swing"), P("intensity")),
        "arm_r": neg(S("arm")),
    }
    root = {
        "dx": mul(S("lean"), 4),
        # bob 已是 y 位移（负=上），直接作为根运动传给躯干
        "dy": S("bob"),
    }
    offsets = {
        "front": {
            "legs": {
                "ankle_left": xy(y=mul(S("lift"), P("step_height"), -20)),
                "ankle_right": xy(y=mul(S("lift_r"), P("step_height"), -20)),
            },
            "pelvis": {
                "pelvis": xy(x=mul(S("sway"), 3)),
                "hip_left": xy(x=mul(S("sway"), 3)),
                "hip_right": xy(x=mul(S("sway"), 3)),
                "iliac_left": xy(x=mul(S("sway"), 3)),
                "iliac_right": xy(x=mul(S("sway"), 3)),
                # 对侧旋转：骨盆摆右时左肩微后、右肩微前（肩带扭转，±1 保骨长）
                "shoulder_left": xy(x=mul(S("sway"), -1)),
                "shoulder_right": xy(x=mul(S("sway"), 1)),
                "clavicle_left": xy(x=mul(S("sway"), -1)),
                "clavicle_right": xy(x=mul(S("sway"), 1)),
            },
            # 左右臂反相（左腿前迈→左臂后摆下沉、右臂前摆上抬）；
            # x 用 arm 同相（后摆向中心/前摆向外），镜像对称。
            "arms": front_hands(mul(S("arm"), 5), mul(S("arm"), 8),
                               mul(S("arm"), 5), mul(S("arm_r"), 8)),
        },
        "side": {
            "legs": {
                # 对称开合（cos2）：每步一次并拢(过位 f2/f6)+张开(f0/f4)，
                # rear/front 永不越位（近侧腿恒在前），左右步态几何对称。
                # 抬脚与开合同步：f1-3 rear 腿迈步并拢、f5-7 front 腿迈步并拢。
                "rear_ankle": xy(
                    x=mul(add(1.0, neg(cos(mul(PH(), 2.0)))), P("stride"), 13),
                    y=mul(S("lift"), P("step_height"), -22)),
                "front_ankle": xy(
                    x=mul(add(1.0, neg(cos(mul(PH(), 2.0)))), P("stride"), -13),
                    y=mul(S("lift_r"), P("step_height"), -22)),
            },
            "pelvis": {
                # 躯干反向扭转：骨盆摆向一侧，上躯干摆向另一侧
                "waist": xy(x=mul(S("sway"), -2)),
                "sternum": xy(x=mul(S("sway"), -2.5)),
                "chest": xy(x=mul(S("sway"), -3)),
                "upper_chest": xy(x=mul(S("sway"), -3)),
                "neck": xy(x=mul(S("sway"), -3)),
                "jaw": xy(x=mul(S("sway"), -3)),
                "clavicle_front": xy(x=mul(S("sway"), -3)),
                "clavicle_rear": xy(x=mul(S("sway"), -3)),
                "front_shoulder": xy(x=mul(S("sway"), -3)),
                "rear_shoulder": xy(x=mul(S("sway"), -3)),
                "rib_front": xy(x=mul(S("sway"), -3)),
                "rib_rear": xy(x=mul(S("sway"), -3)),
            },
            # 手腕前后摆 + 弧线：前摆上抬(y 负)/后摆下沉(y 正)
            "arms": {
                **side_hands(mul(S("arm"), 20), mul(S("arm"), -10),
                            mul(S("arm_r"), 20), mul(S("arm_r"), -10)),
            },
        },
        "back": {
            "legs": {
                "rear_ankle_left": xy(y=mul(S("lift"), P("step_height"), -20)),
                "rear_ankle_right": xy(y=mul(S("lift_r"), P("step_height"), -20)),
            },
            "pelvis": {
                "pelvis": xy(x=mul(S("sway"), 3)),
                "rear_hip_left": xy(x=mul(S("sway"), 3)),
                "rear_hip_right": xy(x=mul(S("sway"), 3)),
            },
            "arms": back_hands(mul(S("arm"), -5), mul(S("arm"), 8),
                              mul(S("arm"), 5), mul(S("arm_r"), 8)),
        },
    }
    return motion(
        "walk", "Walk — 8 帧标准行走",
        "接触/过位/最低/最高关键帧驱动的标准行走循环：腿部跨步+抬脚（IK 屈膝），"
        "骨盆起伏+侧摆，躯干反向扭转，肩部带动摆臂，前倾保持动态平衡。",
        params, signals, offsets, root, walk_selectors(), ik_groups())


# ------------------------------------------------------------------- run


def build_run():
    params = {
        "intensity": knob(1.0, 0.0, 1.5, 0.05, "力度协调",
                          "主参数：协调腾空/提膝/摆臂等整体强度"),
        "stride": knob(1.0, 0.0, 2.0, 0.05, "步幅",
                       "腿部前后跨步幅度（大于行走）"),
        "flight": knob(1.0, 0.0, 2.0, 0.05, "腾空",
                       "身体垂直起伏 + 脚离地高度（腾空相）"),
        "knee_drive": knob(1.0, 0.0, 2.0, 0.05, "提膝",
                           "前摆高抬膝（驱动脚前送高度）"),
        "heel_kick": knob(1.0, 0.0, 2.0, 0.05, "后撩",
                          "后摆脚跟撩起高度（支撑腿蹬地）"),
        "torso_lean": knob(1.0, 0.0, 2.0, 0.05, "前倾",
                           "上身前倾幅度（跑步动态平衡，大于行走）"),
        "arm_swing": knob(1.0, 0.0, 2.0, 0.05, "摆臂",
                          "摆臂幅度（屈肘约 90°，肩部带动）"),
    }
    signals = {
        "phase": PH(),
        "swing": mul(sin(PH()), P("stride"), P("intensity")),
        "swing_r": neg(S("swing")),
        # 腾空：身体起伏（两上两下，过位腾空最高）；×8 跑步垂直位移大于行走
        "bob": mul(cos(mul(PH(), 2.0)), P("flight"), P("intensity"), 8.0),
        "sway": mul(sin(PH()), P("intensity")),
        "lean": mul(P("torso_lean"), P("intensity")),
        "arm": mul(sin(PH()), P("arm_swing"), P("intensity")),
        "arm_r": neg(S("arm")),
        # 左脚/后脚高度：基础腾空 + 前摆提膝 + 后摆后撩（右/前脚镜像，table 已平滑）
        "flight_l": mul(table(0.5, 0.7, 0.5, 0.15, 0.05, 0.2, 0.5, 0.7), P("intensity")),
        "drive_l": mul(table(0.5, 0.8, 0.5, 0.15, 0.0, 0.05, 0.15, 0.3), P("intensity")),
        "kick_l": mul(table(0.0, 0.0, 0.05, 0.0, 0.05, 0.3, 0.7, 0.5), P("intensity")),
        "flight_r": mul(table(0.05, 0.2, 0.5, 0.7, 0.5, 0.7, 0.5, 0.15), P("intensity")),
        "drive_r": mul(table(0.0, 0.05, 0.15, 0.3, 0.5, 0.8, 0.5, 0.15), P("intensity")),
        "kick_r": mul(table(0.05, 0.3, 0.7, 0.5, 0.0, 0.0, 0.05, 0.0), P("intensity")),
    }

    def foot_h(flight_sig, drive_sig, kick_sig):
        # 高度 = flight*基础腾空 + knee_drive*前摆 + heel_kick*后撩
        return mul(
            add(mul(S(flight_sig), P("flight")),
                mul(S(drive_sig), P("knee_drive")),
                mul(S(kick_sig), P("heel_kick"))),
            -13)

    root = {
        "dx": mul(S("lean"), 5),
        "dy": neg(S("bob")),
    }
    offsets = {
        "front": {
            "legs": {
                "ankle_left": xy(y=foot_h("flight_l", "drive_l", "kick_l")),
                "ankle_right": xy(y=foot_h("flight_r", "drive_r", "kick_r")),
            },
            "pelvis": {
                "pelvis": xy(x=mul(S("sway"), 3)),
                "hip_left": xy(x=mul(S("sway"), 3)),
                "hip_right": xy(x=mul(S("sway"), 3)),
                "iliac_left": xy(x=mul(S("sway"), 3)),
                "iliac_right": xy(x=mul(S("sway"), 3)),
            },
            "arms": front_hands(mul(S("arm"), -4), mul(S("arm"), 6),
                               mul(S("arm"), 4), mul(S("arm_r"), 6)),
        },
        "side": {
            "legs": {
                "rear_ankle": xy(x=mul(S("swing"), 30), y=foot_h("flight_l", "drive_l", "kick_l")),
                "front_ankle": xy(x=mul(S("swing_r"), 30), y=foot_h("flight_r", "drive_r", "kick_r")),
            },
            "pelvis": {
                "waist": xy(x=mul(S("sway"), -2)),
                "sternum": xy(x=mul(S("sway"), -2.5)),
                "chest": xy(x=mul(S("sway"), -3)),
                "upper_chest": xy(x=mul(S("sway"), -3)),
                "neck": xy(x=mul(S("sway"), -3)),
                "jaw": xy(x=mul(S("sway"), -3)),
                "clavicle_front": xy(x=mul(S("sway"), -3)),
                "clavicle_rear": xy(x=mul(S("sway"), -3)),
                "front_shoulder": xy(x=mul(S("sway"), -3)),
                "rear_shoulder": xy(x=mul(S("sway"), -3)),
                "rib_front": xy(x=mul(S("sway"), -3)),
                "rib_rear": xy(x=mul(S("sway"), -3)),
            },
            "arms": {
                **side_hands(mul(S("arm"), 18), mul(S("arm"), 10),
                            mul(S("arm_r"), 18), mul(S("arm_r"), 10)),
            },
        },
        "back": {
            "legs": {
                "rear_ankle_left": xy(y=foot_h("flight_l", "drive_l", "kick_l")),
                "rear_ankle_right": xy(y=foot_h("flight_r", "drive_r", "kick_r")),
            },
            "pelvis": {
                "pelvis": xy(x=mul(S("sway"), 3)),
                "rear_hip_left": xy(x=mul(S("sway"), 3)),
                "rear_hip_right": xy(x=mul(S("sway"), 3)),
            },
            "arms": back_hands(mul(S("arm"), -4), mul(S("arm"), 6),
                              mul(S("arm"), 4), mul(S("arm_r"), 6)),
        },
    }
    return motion(
        "run", "Run — 弹跳跑步循环",
        "带腾空相的跑步循环：双脚离地（腾空），前摆高抬膝、后摆脚跟后撩，"
        "骨盆起伏大于行走，上身前倾，屈肘约 90° 摆臂。",
        params, signals, offsets, root, walk_selectors(), ik_groups())


# ------------------------------------------------------------------ jump


def build_jump():
    params = {
        "intensity": knob(1.0, 0.0, 1.5, 0.05, "力度协调",
                          "主参数：协调起跳/收腿/举臂等整体强度"),
        "height": knob(1.0, 0.0, 2.0, 0.05, "跳跃高度",
                       "起跳腾空高度（身体垂直位移）"),
        "crouch": knob(1.0, 0.0, 2.0, 0.05, "下蹲",
                       "预备下蹲深度（蓄力，膝弯+身体下沉）"),
        "arm_raise": knob(1.0, 0.0, 2.0, 0.05, "举臂",
                          "下摆蓄力/上举腾空的摆臂幅度"),
        "tuck": knob(1.0, 0.0, 2.0, 0.05, "收腿",
                     "滞空收腿幅度（双膝上提）"),
        "land_absorb": knob(1.0, 0.0, 2.0, 0.05, "落地缓冲",
                            "落地屈膝缓冲幅度"),
    }
    signals = {
        "phase": PH(),
        # 下蹲形状（+ = 向下；i=2 最深 ~15px，帧间平滑）
        "squat": mul(table(0.0, 9.0, 15.0, 9.0, 3.0, 2.0, 8.0, 3.0),
                     P("crouch"), P("intensity")),
        # 起跳腾空形状（+ = 向上，用 neg 取负；i=4 最高 ~16px，平滑上升）
        "rise": mul(table(0.0, 0.0, 0.0, 6.0, 16.0, 14.0, 8.0, 2.0),
                    P("height"), P("intensity")),
        # 落地缓冲（+ = 向下；i=6 落地 ~10px）
        "land": mul(table(0.0, 0.0, 0.0, 0.0, 0.0, 3.0, 10.0, 5.0),
                    P("land_absorb"), P("intensity")),
        # 脚离地（腾空）：基础 + 收腿，平滑过渡
        "air_foot": mul(table(0.0, 0.0, 2.0, 8.0, 20.0, 18.0, 11.0, 4.0),
                        P("height"), P("intensity")),
        "tuck_foot": mul(table(0.0, 0.0, 0.0, 2.0, 8.0, 8.0, 3.0, 0.0),
                         P("tuck"), P("intensity")),
        # 摆臂（+ = 手向下/后，- = 手上举）；下摆→上举平滑过渡避免 14px 突跳
        "arm": mul(table(0.0, 4.0, 8.0, 1.0, -6.0, -14.0, -9.0, -2.0),
                   P("arm_raise"), P("intensity")),
    }
    root = {
        "dx": 0,
        "dy": add(S("squat"), neg(S("rise")), S("land")),
    }
    offsets = {
        "front": {
            "legs": {
                "ankle_left": xy(y=neg(add(S("air_foot"), S("tuck_foot")))),
                "ankle_right": xy(y=neg(add(S("air_foot"), S("tuck_foot")))),
            },
            "arms": front_hands(None, S("arm"), None, S("arm")),
        },
        "side": {
            "legs": {
                "rear_ankle": xy(y=neg(add(S("air_foot"), S("tuck_foot")))),
                "front_ankle": xy(y=neg(add(S("air_foot"), S("tuck_foot")))),
            },
            "arms": side_hands(None, S("arm"), None, S("arm")),
        },
        "back": {
            "legs": {
                "rear_ankle_left": xy(y=neg(add(S("air_foot"), S("tuck_foot")))),
                "rear_ankle_right": xy(y=neg(add(S("air_foot"), S("tuck_foot")))),
            },
            "arms": back_hands(None, S("arm"), None, S("arm")),
        },
    }
    selectors = {
        "front_leg": {"const": "left"},
        "foreground_leg": {"const": "front"},
        "foreground": {"const": "left"},
    }
    return motion(
        "jump", "Jump — 蹲/起跳/滞空/落地循环",
        "四阶段跳跃：预备下蹲（蓄力）→ 起跳爆发 → 滞空收腿 → 落地屈膝缓冲。"
        "双臂下摆蓄力后上举，IK 保持腿长使膝弯自然。",
        params, signals, offsets, root, selectors, ik_groups())


# ----------------------------------------------------------------- idle


def build_idle():
    params = {
        "intensity": knob(1.0, 0.0, 1.5, 0.05, "力度协调",
                          "主参数：协调呼吸/胸廓/耸肩等整体强度"),
        "breath": knob(1.0, 0.0, 2.0, 0.05, "呼吸",
                       "呼吸起伏（骨盆微沉、头肩微动）"),
        "chest_expand": knob(1.0, 0.0, 2.0, 0.05, "胸廓",
                            "肋骨外扩、胸腔开合幅度"),
        "shoulder_rise": knob(1.0, 0.0, 2.0, 0.05, "耸肩",
                              "随呼吸的肩部起伏幅度"),
        "weight_shift": knob(1.0, 0.0, 2.0, 0.05, "重心",
                             "轻微左右重心偏移"),
        "arm_sway": knob(1.0, 0.0, 2.0, 0.05, "手臂",
                        "手臂自然轻摆幅度"),
    }
    signals = {
        "phase": PH(),
        # 呼吸波（8 帧一呼一吸）
        "breath": mul(sin(PH()), P("breath"), P("intensity")),
        "chest": mul(sin(PH()), P("chest_expand"), P("intensity")),
        "shoulder": mul(sin(PH()), P("shoulder_rise"), P("intensity")),
        "sway": mul(sin(PH()), P("weight_shift"), P("intensity")),
        "arm": mul(sin(PH()), P("arm_sway"), P("intensity")),
        "arm_r": neg(S("arm")),
    }
    root = {
        "dx": mul(S("sway"), 1.5),
        "dy": mul(S("breath"), -1.2),
    }
    offsets = {
        "front": {
            "pelvis": {
                # 胸腔开合：肋骨外扩
                "rib_upper_left": xy(x=mul(S("chest"), -1.2)),
                "rib_upper_right": xy(x=mul(S("chest"), 1.2)),
                "rib_lower_left": xy(x=mul(S("chest"), -0.9)),
                "rib_lower_right": xy(x=mul(S("chest"), 0.9)),
                # 耸肩
                "shoulder_left": xy(y=mul(S("shoulder"), -1.2)),
                "shoulder_right": xy(y=mul(S("shoulder"), -1.2)),
                "clavicle_left": xy(y=mul(S("shoulder"), -1.2)),
                "clavicle_right": xy(y=mul(S("shoulder"), -1.2)),
                # 重心偏移
                "pelvis": xy(x=mul(S("sway"), 1.2)),
                "hip_left": xy(x=mul(S("sway"), 1.2)),
                "hip_right": xy(x=mul(S("sway"), 1.2)),
                "iliac_left": xy(x=mul(S("sway"), 1.2)),
                "iliac_right": xy(x=mul(S("sway"), 1.2)),
            },
            "arms": front_hands(mul(S("arm_r"), 3), mul(S("arm_r"), 4),
                               mul(S("arm"), 3), mul(S("arm"), 4)),
        },
        "side": {
            "pelvis": {
                "rib_front": xy(y=mul(S("chest"), 0.8)),
                "rib_rear": xy(y=mul(S("chest"), 0.6)),
                "front_shoulder": xy(y=mul(S("shoulder"), -1.2)),
                "rear_shoulder": xy(y=mul(S("shoulder"), -1.0)),
                "clavicle_front": xy(y=mul(S("shoulder"), -1.2)),
                "clavicle_rear": xy(y=mul(S("shoulder"), -1.0)),
            },
            "arms": side_hands(mul(S("arm"), 3), mul(S("arm"), 2.5),
                              mul(S("arm_r"), 3), mul(S("arm_r"), 2.5)),
        },
        "back": {
            "pelvis": {
                "rib_upper_left": xy(x=mul(S("chest"), -1.2)),
                "rib_upper_right": xy(x=mul(S("chest"), 1.2)),
                "rear_shoulder_left": xy(y=mul(S("shoulder"), -1.2)),
                "rear_shoulder_right": xy(y=mul(S("shoulder"), -1.2)),
            },
            "arms": back_hands(mul(S("arm_r"), 3), mul(S("arm_r"), 4),
                              mul(S("arm"), 3), mul(S("arm"), 4)),
        },
    }
    selectors = {
        "front_leg": {"const": "left"},
        "foreground_leg": {"const": "front"},
        "foreground": {"const": "left"},
    }
    return motion(
        "idle", "Idle — 待机呼吸",
        "呼吸待机：胸腔开合、耸肩、骨盆微沉、重心轻微偏移、手臂自然轻摆。",
        params, signals, offsets, root, selectors, ik_groups())


# ------------------------------------------------------------------ main


def main():
    for builder in (build_walk, build_run, build_jump, build_idle):
        data = builder()
        bad = validate(data)
        if bad:
            print(f"!! {data['motion_id']}: unknown joints: {bad}")
        write(data["motion_id"], data)
    print("\nDone.")


if __name__ == "__main__":
    main()
