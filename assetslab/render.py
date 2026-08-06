#!/usr/bin/env python3
"""Render skeleton pipeline previews with Pillow (pure Python, no Godot).

Skeletons are defined in assetslab/presets/<id>.json.
Species templates are in assetslab/species/<id>.json.
Use --skeleton to select which preset to render (default: standard).

Pose math is ported from the GDScript stage models so the output matches the
Godot headless capture (colors, line widths, anchors).  Parameters let AI or a
human tune the pose directly:

    --skeleton   skeleton id (standard, female, ...)
    --stride      leg swing amplitude multiplier
    --pelvis-bob  pelvis bob multiplier (stage 3)
    --arm-swing   arm swing multiplier (stage 4)
    --style       consistent (same look as Godot) | simple

Outputs (into the skeleton pipeline dir, same names as the Godot capture):
    skeleton  -> {view}_base.png
    legs/pelvis/arms -> {prefix}_8frames.png + {prefix}.gif
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
from pathlib import Path

from PIL import Image, ImageDraw

W, H = 960, 600
FLOOR_Y = 470.0
CENTER_X = 480.0
ROOT_X = 480.0
FRAME_COUNT = 8
TAU = math.tau

BG = (17, 24, 39)          # 111827
GUIDE = (75, 94, 122)      # 4b5e7a
BONE = (157, 214, 255)     # 9dd6ff
JOINT = (255, 241, 168)    # fff1a8
REAR = (127, 159, 196)     # 7f9fc4
FRONT = (255, 210, 122)    # ffd27a
PELVIS_C = (255, 188, 115) # ffbc73
ARM = (169, 232, 195)      # a9e8c3
DARK = (30, 58, 95)        # 1e3a5f
BONE_DARK = (30, 42, 63)   # 1e3a5f
HEAD_DARK = (35, 51, 74)   # 23334a
OUTLINE = (90, 130, 170)    # body outline color

ROOT = Path(__file__).resolve().parents[1]  # repo root (assetslab/ → repo)
PKG_ROOT = Path(__file__).resolve().parent   # assetslab/
PRESETS_ROOT = PKG_ROOT / "presets"
SPECIES_ROOT = PKG_ROOT / "species"
SKELETONS_ROOT = PKG_ROOT / "presets"  # primary lookup
DEFAULT_OUTPUT = ROOT / "prototype" / "test_output" / "skeleton_pipeline"

PREFIX = {
    ("front", "legs"): "front_legs",
    ("front", "pelvis"): "front_pelvis_bob",
    ("front", "arms"): "front_arm_swing",
    ("side", "legs"): "side_legs",
    ("side", "pelvis"): "side_pelvis_bob",
    ("side", "arms"): "side_arm_swing",
    ("back", "legs"): "back_legs",
}


# ------------------------------------------------------------------ canvas --


def canvas():
    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)
    draw.line([(160, FLOOR_Y), (800, FLOOR_Y)], fill=GUIDE, width=2)
    return image, draw


def bone(draw, a, b, color, width=7):
    draw.line([a, b], fill=BONE_DARK, width=width + 6)
    draw.line([a, b], fill=color, width=width)


def head(draw, center, color=BONE, radius=24, width=3):
    """Draw head as a tall oval (model proportion, taller than wide)."""
    cx, cy = center
    rx, ry = int(radius * 0.78), radius  # tall oval: clearly narrower than tall
    box = (cx - rx, cy - ry, cx + rx, cy + ry)
    draw.ellipse(box, fill=(45, 60, 90), outline=color, width=width)


def joint(draw, point, color=JOINT, radius=7):
    box = (point[0] - radius, point[1] - radius, point[0] + radius, point[1] + radius)
    draw.ellipse(box, fill=color, outline=HEAD_DARK, width=2)


def pelvis(draw, point):
    box = (point[0] - 14, point[1] - 14, point[0] + 14, point[1] + 14)
    draw.ellipse(box, fill=PELVIS_C, outline=(77, 43, 32), width=2)


def torso_outline_front(draw, base):
    """正面躯干轮廓：沙漏形（窄肩→胸→收腰→宽髋），女性比例。"""
    cx = base["chest"][0]
    # 女性比例调整：肩略窄、腰收、髋略宽
    sh_lx = base["shoulder_left"][0] + 8    # 肩内收
    sh_rx = base["shoulder_right"][0] - 8
    chest_w = 34  # 胸部半宽
    waist_w = 22  # 腰部半宽（收紧）
    hip_w = 38    # 髋部半宽（略宽于肩）
    pts = [
        (sh_lx, base["shoulder_left"][1]),
        (cx - chest_w, base["chest"][1]),
        (cx - waist_w, base["waist"][1]),
        (base["hip_left"][0] - 2, base["hip_left"][1]),
        # 腿部外侧轮廓
        (base["hip_left"][0] - 6, base["knee_left"][1]),
        (base["foot_left"][0] - 4, base["foot_left"][1]),
        (base["foot_right"][0] + 4, base["foot_right"][1]),
        (base["hip_right"][0] + 6, base["knee_right"][1]),
        (base["hip_right"][0] + 2, base["hip_right"][1]),
        (cx + waist_w, base["waist"][1]),
        (cx + chest_w, base["chest"][1]),
        (sh_rx, base["shoulder_right"][1]),
    ]
    draw.line(pts, fill=OUTLINE, width=2)


def torso_outline_side(draw, base):
    """侧面躯干轮廓：女性S曲线（胸凸+腰收+臀翘）。"""
    cx = base["chest"][0]
    # 侧面：前侧(+x)为胸/腹，后侧(-x)为背/臀
    chest_fwd = 32   # 胸部前凸
    waist_fwd = 18   # 腰前收
    hip_fwd = 24     # 髋前
    back_upper = 22  # 上背
    back_waist = 16  # 腰后
    back_hip = 28    # 臀后凸
    pts = [
        (cx - back_upper, base["neck"][1]),       # 后颈
        (cx - back_upper + 2, base["chest"][1]),   # 后背
        (cx - back_waist, base["waist"][1]),        # 后腰
        (cx - back_hip, base["pelvis"][1]),          # 后臀
        # 后腿
        (base["rear_hip"][0] - 8, base["rear_knee"][1]),
        (base["rear_foot"][0] - 4, base["rear_foot"][1]),
        (base["front_foot"][0] + 4, base["front_foot"][1]),
        (base["front_hip"][0] + 8, base["front_knee"][1]),
        # 前躯干
        (cx + hip_fwd, base["pelvis"][1]),           # 前髋
        (cx + waist_fwd, base["waist"][1]),           # 前腰
        (cx + chest_fwd, base["chest"][1]),           # 前胸
        (cx + chest_fwd - 4, base["neck"][1]),        # 前颈
    ]
    draw.line(pts, fill=OUTLINE, width=2)


def torso_outline_back(draw, base):
    """背面躯干轮廓：背阔肌→腰收→臀宽。"""
    cx = base["chest"][0]
    back_w = 36   # 背阔半宽
    waist_w = 22  # 腰半宽
    hip_w = 36    # 臀半宽
    pts = [
        (base["rear_shoulder_left"][0] + 4, base["rear_shoulder_left"][1]),
        (cx - back_w, base["chest"][1]),
        (cx - waist_w, base["waist"][1]),
        (base["rear_hip_left"][0] - 4, base["rear_hip_left"][1]),
        (base["rear_hip_left"][0] - 8, base["rear_knee_left"][1]),
        (base["rear_foot_left"][0] - 4, base["rear_foot_left"][1]),
        (base["rear_foot_right"][0] + 4, base["rear_foot_right"][1]),
        (base["rear_hip_right"][0] + 8, base["rear_knee_right"][1]),
        (base["rear_hip_right"][0] + 4, base["rear_hip_right"][1]),
        (cx + waist_w, base["waist"][1]),
        (cx + back_w, base["chest"][1]),
        (base["rear_shoulder_right"][0] - 4, base["rear_shoulder_right"][1]),
    ]
    draw.line(pts, fill=OUTLINE, width=2)


# ------------------------------------------------------------------ skeleton loading --

_SKELETON: dict | None = None
_SKELETON_ID: str = "standard"


def _find_skeleton_file(skeleton_id: str) -> Path | None:
    """Find a preset or species skeleton file.
    Presets: presets/<id>.json
    Species: species/<id>/skeleton.json"""
    # Presets first (flat JSON)
    p = PRESETS_ROOT / f"{skeleton_id}.json"
    if p.exists():
        return p
    # Species (folder with skeleton.json)
    p = SPECIES_ROOT / skeleton_id / "skeleton.json"
    if p.exists():
        return p
    # Backward compat
    p = SKELETONS_ROOT / f"{skeleton_id}.json"
    if p.exists():
        return p
    return None


def load_skeleton_json(skeleton_id: str = "standard") -> dict:
    """Load skeleton from assetslab/presets/<id>.json (or species/ fallback).
    Handles v3 preset format (references species template) and v2/v3 full format."""
    path = _find_skeleton_file(skeleton_id)
    if path is None:
        raise SystemExit(f"Skeleton not found: {skeleton_id}")
    
    import json
    data = json.loads(path.read_text(encoding="utf-8"))
    
    # v3 preset format: references a species template
    species_ref = data.get("species") or data.get("skeleton")
    if species_ref and "positions" in data and "preset_id" in data:
        template_id = species_ref
        template_path = _find_skeleton_file(template_id)
        if template_path is None:
            raise SystemExit(f"Species template not found: {template_id}")
        template = json.loads(template_path.read_text(encoding="utf-8"))
        
        views = data["positions"]
        # Apply aliases
        aliases = template.get("joints", {}).get("aliases", {})
        for view_name in list(views.keys()):
            v = views[view_name]
            for alias, target in aliases.items():
                if target in v and alias not in v:
                    v[alias] = v[target][:]
        
        # Build torso from template's torso_joints
        torso_joints = template.get("torso_joints", [])
        torso = {}
        for view_name in views:
            torso[view_name] = {j: 1.0 for j in torso_joints if j in views[view_name]}
            for j in views[view_name]:
                if "knee" in j:
                    torso[view_name][j] = 0.5
            torso[view_name]["head"] = 0.5
        
        upper_list = template.get("upper_joints", [])
        upper_joints = {vn: [j for j in upper_list if j in views.get(vn, {})] for vn in views}
        
        # Build chains from template
        chains = template.get("chains", {})
        arm_chains = {}
        leg_chains = {}
        for side, prefix in [("left", "arm_left"), ("right", "arm_right")]:
            chain = chains.get(prefix, [])
            if len(chain) >= 2:
                arm_chains.setdefault("front", {})[chain[0]] = chain[1:]
        for side, prefix in [("left", "leg_left"), ("right", "leg_right")]:
            chain = chains.get(prefix, [])
            if len(chain) >= 2:
                leg_chains.setdefault("front", {})[chain[0]] = chain[1:]
        
        return {
            "skeleton_id": data["preset_id"],
            "schema": "assetslab_skeleton_v3",
            "title": data.get("title", ""),
            "description": data.get("description", ""),
            "canvas": data.get("canvas", {"width": 960, "height": 600, "floor_y": 470}),
            "head_radius": data.get("head_radius", 24),
            "body": data.get("body", {}),
            "views": views,
            "bones": template.get("bones", {}),
            "joints": template.get("joints", {}),
            "torso": data.get("torso_inherit", torso),
            "params": data.get("params", template.get("params", {})),
            "param_chains": template.get("param_chains", {}),
            "arm_chains": arm_chains,
            "leg_chains": leg_chains,
            "upper_joints": upper_joints,
        }
    
    # v2/v3 full skeleton format
    return data


def set_skeleton(skeleton_id: str = "standard") -> dict:
    """Switch active skeleton, returns the skeleton dict."""
    global _SKELETON, _SKELETON_ID
    _SKELETON = load_skeleton_json(skeleton_id)
    _SKELETON_ID = skeleton_id
    return _SKELETON


def skeleton_views() -> dict:
    """Return {view: {joint_name: (x, y)}} for the active skeleton."""
    global _SKELETON
    if _SKELETON is None:
        _SKELETON = load_skeleton_json("standard")
    return {view: {name: (float(x), float(y)) for name, (x, y) in joints.items()}
            for view, joints in _SKELETON.get("views", {}).items()}


# Initialize default skeleton
set_skeleton("standard")


def front_base() -> dict:
    """Front view base joints from active skeleton."""
    return skeleton_views().get("front", {})


def side_base() -> dict:
    """Side view base joints from active skeleton."""
    return skeleton_views().get("side", {})


def back_base() -> dict:
    """Back view base joints from active skeleton."""
    return skeleton_views().get("back", {})


def vadd(a, b):
    return (a[0] + b[0], a[1] + b[1])


def vmul(a, k):
    return (a[0] * k, a[1] * k)


# ------------------------------------------------------------------- poses --


def phase(index):
    return TAU * float(index % FRAME_COUNT) / float(FRAME_COUNT)


def front_leg_pose(index, stride=1.0):
    base = front_base()
    swing = math.sin(phase(index)) * stride
    rswing = -swing
    return {
        "left_hip": base["hip_left"], "right_hip": base["hip_right"],
        "left_knee": (448.0 + swing * 15.0, 415.0 - max(0.0, swing) * 22.0),
        "right_knee": (512.0 + rswing * 15.0, 415.0 - max(0.0, rswing) * 22.0),
        "left_foot": (448.0 + swing * 24.0, FLOOR_Y - max(0.0, swing) * 26.0),
        "right_foot": (512.0 + rswing * 24.0, FLOOR_Y - max(0.0, rswing) * 26.0),
        "front_leg": "left" if index < 4 else "right",
    }


def front_pelvis_pose(index, stride=1.0, bob=1.0):
    offsets = [-2.0, -1.0, 1.0, 3.0, -2.0, -1.0, 1.0, 3.0]
    pose = front_leg_pose(index, stride)
    dy = offsets[index % FRAME_COUNT] * bob
    base = front_base()
    # Root-driven rigid torso: the pelvis movement inherits into the whole
    # upper body (hips/shoulders/arms rigid at 1.0, knees damped at 0.5, and
    # the head damped at 0.5 to keep the line of sight stable).
    pose["pelvis"] = vadd(base["pelvis"], (0.0, dy))
    pose["left_hip"] = vadd(base["hip_left"], (0.0, dy))
    pose["right_hip"] = vadd(base["hip_right"], (0.0, dy))
    pose["chest"] = vadd(base["chest"], (0.0, dy))
    pose["waist"] = vadd(base["waist"], (0.0, dy))
    for joint in ("shoulder_left", "shoulder_right",
                  "elbow_left", "elbow_right", "hand_left", "hand_right"):
        pose[joint] = vadd(base[joint], (0.0, dy))
    pose["left_knee"] = vadd(pose["left_knee"], vmul((0.0, dy), 0.5))
    pose["right_knee"] = vadd(pose["right_knee"], vmul((0.0, dy), 0.5))
    pose["neck"] = vadd(base["neck"], (0.0, dy))
    pose["head"] = vadd(base["head"], (0.0, dy * 0.5))
    return pose


def front_arm_pose(index, swing=1.0, bob=1.0):
    base = front_base()
    offsets = [-2.0, -1.0, 1.0, 3.0, -2.0, -1.0, 1.0, 3.0]
    dy = offsets[index % FRAME_COUNT] * bob
    left = -math.sin(phase(index)) * swing
    right = -left
    return {
        "left_elbow": vadd(vadd(base["elbow_left"], vmul((5.0, 6.0), left)), (0.0, dy)),
        "left_hand": vadd(vadd(base["hand_left"], vmul((10.0, 14.0), left)), (0.0, dy)),
        "right_elbow": vadd(vadd(base["elbow_right"], vmul((5.0, 6.0), right)), (0.0, dy)),
        "right_hand": vadd(vadd(base["hand_right"], vmul((10.0, 14.0), right)), (0.0, dy)),
    }


def side_lift(index, leg_name):
    local = index % FRAME_COUNT
    if leg_name == "rear" and local in (1, 2, 3):
        return math.sin(math.pi * local / 4.0)
    if leg_name == "front" and local in (5, 6, 7):
        return math.sin(math.pi * (local - 4) / 4.0)
    return 0.0


def side_leg_pose(index, stride=1.0):
    base = side_base()
    s = math.cos(phase(index)) * stride
    rear_lift = side_lift(index, "rear")
    front_lift = side_lift(index, "front")
    return {
        "rear_hip": base["rear_hip"], "front_hip": base["front_hip"],
        "rear_knee": (ROOT_X - 18.0 * s, 414.0 - rear_lift * 20.0),
        "front_knee": (ROOT_X + 18.0 * s, 410.0 - front_lift * 20.0),
        "rear_foot": (ROOT_X + 2.0 - 30.0 * s, FLOOR_Y - rear_lift * 30.0),
        "front_foot": (ROOT_X + 2.0 + 30.0 * s, FLOOR_Y - front_lift * 30.0),
        "foreground_leg": "front" if index == 0 or index >= 5 else "rear",
    }


def side_pelvis_pose(index, stride=1.0, bob=1.0):
    offsets = [-2.0, -1.0, 1.0, 3.0, -2.0, -1.0, 1.0, 3.0]
    pose = side_leg_pose(index, stride)
    dy = offsets[index % FRAME_COUNT] * bob
    base = side_base()
    # Root-driven rigid torso (side view): shoulders/arms ride the pelvis bob.
    for joint in ("pelvis", "chest", "waist", "rear_hip", "front_hip",
                  "rear_shoulder", "front_shoulder",
                  "rear_elbow", "front_elbow", "rear_hand", "front_hand"):
        pose[joint] = vadd(base[joint], (0.0, dy))
    # head: vertical bob at half pelvis amplitude + forward/back sway per stride
    hx = math.cos(phase(index)) * 4.0
    pose["head"] = (base["head"][0] + hx, base["head"][1] + dy * 0.5)
    pose["neck"] = (base["neck"][0] + hx, base["neck"][1] + dy)
    return pose


def side_arm_pose(index, swing=1.0, bob=1.0):
    base = side_base()
    offsets = [-2.0, -1.0, 1.0, 3.0, -2.0, -1.0, 1.0, 3.0]
    dy = offsets[index % FRAME_COUNT] * bob
    s = math.cos(phase(index)) * swing
    rear_offset = vmul((7.0, 3.0), s)
    front_offset = vmul(rear_offset, -1.0)
    return {
        "rear_elbow": vadd(vadd(base["rear_elbow"], rear_offset), (0.0, dy)),
        "rear_hand": vadd(vadd(base["rear_hand"], vmul(rear_offset, 2.0)), (0.0, dy)),
        "front_elbow": vadd(vadd(base["front_elbow"], front_offset), (0.0, dy)),
        "front_hand": vadd(vadd(base["front_hand"], vmul(front_offset, 2.0)), (0.0, dy)),
    }


def back_leg_pose(index, stride=1.0, bob=1.0):
    base = back_base()
    s = math.sin(phase(index)) * stride
    r = -s
    # head bob on the back view uses the same pelvis-bob table (half amplitude)
    bob_offsets = [-2.0, -1.0, 1.0, 3.0, -2.0, -1.0, 1.0, 3.0]
    dy = bob_offsets[index % FRAME_COUNT] * bob * 0.5
    return {
        "left_hip": base["front_hip_left"], "right_hip": base["front_hip_right"],
        "left_knee": (456 + s * 15, 410 - max(0.0, s) * 22),
        "right_knee": (504 + r * 15, 410 - max(0.0, r) * 22),
        "left_foot": (456 + s * 24, FLOOR_Y - max(0.0, s) * 26),
        "right_foot": (504 + r * 24, FLOOR_Y - max(0.0, r) * 26),
        "head": (base["head"][0], base["head"][1] + dy),
        "neck": (base["neck"][0], base["neck"][1] + dy),
        "foreground": "left" if index < 4 else "right",
    }


# ------------------------------------------------------------------ render --

# Which joints are "leg" joints (drawn with colored limb styling in animation)
_LEG_JOINTS = {"hip", "knee", "foot"}

def _get_active_skeleton():
    """Return the currently loaded skeleton dict (with bones, views, etc)."""
    global _SKELETON
    if _SKELETON is None:
        _SKELETON = load_skeleton_json("standard")
    return _SKELETON


def _resolve(pt, pose, base):
    """Return animated position if pose has it, else static base position."""
    return pt if isinstance(pt, tuple) else pose.get(pt, base.get(pt, (0, 0)))


def _valid(pt) -> bool:
    """True if a resolved point is a real joint position (not the (0,0) fallback)."""
    return pt is not None and pt != (0, 0)


def _draw_bones_from_def(draw, pose, base, view, skeleton_bones, *, leg_pose=None, arm_pose=None):
    """Data-driven skeleton drawing: reads bone pairs from skeleton['bones'][view]
    and draws them. pose overrides joint positions for animation.

    Bones whose endpoints are missing (resolve to (0,0)) are skipped — this
    prevents phantom lines shooting to the origin for incomplete presets.
    """
    bones = (skeleton_bones or {}).get(view, [])
    if not bones:
        return

    front_leg = leg_pose.get("front_leg") if leg_pose else None
    fg_leg = leg_pose.get("foreground_leg") if leg_pose else None
    fg_side = leg_pose.get("foreground") if leg_pose else None

    for pair in bones:
        a_name, b_name = pair[0], pair[1]
        a = _resolve(a_name, pose, base)
        b = _resolve(b_name, pose, base)
        # 跳过缺失关节的骨骼（避免射向 (0,0) 的幽灵线）
        if not _valid(a) or not _valid(b):
            continue

        color = BONE
        width = 7
        if arm_pose and ("elbow" in a_name or "elbow" in b_name or "hand" in a_name or "hand" in b_name):
            color = ARM
            width = 7
        elif leg_pose:
            tagged = None
            for side_tag, side_color in [(front_leg, FRONT), (fg_leg, FRONT), (fg_side, FRONT)]:
                if side_tag and (side_tag in a_name or side_tag in b_name):
                    tagged = side_color
                    break
            if tagged:
                color = tagged
                width = 8
            else:
                # Rear side detection
                if front_leg:
                    rear_side = "right" if front_leg == "left" else "left"
                    if rear_side in a_name or rear_side in b_name:
                        color, width = REAR, 8
                if fg_leg and color == BONE:
                    rear_side = "rear" if fg_leg == "front" else "front"
                    if rear_side in a_name or rear_side in b_name:
                        color, width = REAR, 8
                if fg_side and color == BONE:
                    rear_side = "right" if fg_side == "left" else "left"
                    if rear_side in a_name or rear_side in b_name:
                        color, width = REAR, 8
            if "hip" in a_name and "hip" in b_name:
                width = 5

        bone(draw, a, b, color, width)

    # Draw joints
    drawn = set()
    for pair in bones:
        for name in pair:
            if name in drawn:
                continue
            drawn.add(name)
            pt = _resolve(name, pose, base)
            if pt and pt != (0, 0):
                joint(draw, pt)

    # Pelvis special marker
    pelvis_pt = _resolve("pelvis", pose, base)
    if pelvis_pt and pelvis_pt != (0, 0):
        pelvis(draw, pelvis_pt)

    # Head circle
    head_pt = _resolve("head", pose, base)
    if head_pt and head_pt != (0, 0):
        head(draw, head_pt)


def render_front_skeleton(image, draw, base):
    skel = _get_active_skeleton()
    torso_outline_front(draw, base)
    _draw_bones_from_def(draw, base, base, "front", skel.get("bones"))


def draw_front_legs(image, draw, pose, base):
    skel = _get_active_skeleton()
    _draw_bones_from_def(draw, pose, base, "front", skel.get("bones"), leg_pose=pose)


def draw_front_arms(image, draw, pose, arms, base):
    skel = _get_active_skeleton()
    merged = dict(pose)
    merged.update(arms)
    _draw_bones_from_def(draw, merged, base, "front", skel.get("bones"), leg_pose=pose, arm_pose=arms)


def render_side_base(image, draw, base):
    skel = _get_active_skeleton()
    torso_outline_side(draw, base)
    _draw_bones_from_def(draw, base, base, "side", skel.get("bones"))


def draw_side_legs(image, draw, pose, base):
    skel = _get_active_skeleton()
    _draw_bones_from_def(draw, pose, base, "side", skel.get("bones"), leg_pose=pose)


def draw_side_arms(image, draw, pose, arms, base):
    skel = _get_active_skeleton()
    merged = dict(pose)
    merged.update(arms)
    _draw_bones_from_def(draw, merged, base, "side", skel.get("bones"), leg_pose=pose, arm_pose=arms)


def render_back_skeleton(image, draw, base):
    skel = _get_active_skeleton()
    torso_outline_back(draw, base)
    _draw_bones_from_def(draw, base, base, "back", skel.get("bones"))


def draw_back_legs(image, draw, pose, base):
    skel = _get_active_skeleton()
    _draw_bones_from_def(draw, pose, base, "back", skel.get("bones"), leg_pose=pose)


# OLD CODE END MARKER - everything above replaces the old render section

def render_frame(view, stage, index, stride, bob, swing, base=None):
    image, draw = canvas()
    if view == "front":
        base = base or front_base()
        if stage == "skeleton":
            render_front_skeleton(image, draw, base)
        elif stage == "legs":
            draw_front_legs(image, draw, front_leg_pose(index, stride), base)
        elif stage == "pelvis":
            draw_front_legs(image, draw, front_pelvis_pose(index, stride, bob), base)
        else:  # arms
            draw_front_arms(image, draw, front_pelvis_pose(index, stride, bob), front_arm_pose(index, swing, bob), base)
    elif view == "side":
        base = base or side_base()
        if stage == "skeleton":
            render_side_base(image, draw, base)
        elif stage == "legs":
            draw_side_legs(image, draw, side_leg_pose(index, stride), base)
        elif stage == "pelvis":
            draw_side_legs(image, draw, side_pelvis_pose(index, stride, bob), base)
        else:  # arms
            draw_side_arms(image, draw, side_pelvis_pose(index, stride, bob), side_arm_pose(index, swing, bob), base)
    else:  # back
        base = base or back_base()
        if stage == "skeleton":
            render_back_skeleton(image, draw, base)
        else:  # legs
            draw_back_legs(image, draw, back_leg_pose(index, stride, bob), base)
    return image


def make_gif(frames, path, duration: int = 125):
    enlarged = [f.resize((480, 300), Image.Resampling.NEAREST) for f in frames]
    # disposal=2 (restore to background): 每帧先清空再绘制，避免后帧叠在前帧上（残影/重叠）
    enlarged[0].save(path, save_all=True, append_images=enlarged[1:], duration=duration, loop=0, disposal=2)


def contact_sheet(frames, path):
    sheet = Image.new("RGB", (480 * 4, 300 * 2), (17, 24, 39))
    for index, frame in enumerate(frames):
        thumb = frame.resize((480, 300), Image.Resampling.NEAREST)
        sheet.paste(thumb, ((index % 4) * 480, (index // 4) * 300))
    sheet.save(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render skeleton pipeline previews with Pillow (no Godot).")
    parser.add_argument("--skeleton", type=str, default="standard",
                        help="Preset id (standard, female, ...) from assetslab/presets/.")
    parser.add_argument("--view", choices=["front", "side", "back"], required=True)
    parser.add_argument("--stage", choices=["skeleton", "legs", "pelvis", "arms"], required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output dir (default: prototype/test_output/skeleton_pipeline).")
    parser.add_argument("--stride", type=float, default=1.0, help="Leg swing amplitude multiplier.")
    parser.add_argument("--pelvis-bob", type=float, default=1.0, help="Pelvis bob multiplier (stage 3).")
    parser.add_argument("--arm-swing", type=float, default=1.0, help="Arm swing multiplier (stage 4).")
    parser.add_argument("--style", choices=["consistent", "simple"], default="consistent", help="consistent = same look as Godot (default).")
    parser.add_argument("--motion", type=str, default=None,
                        help="Data-driven motion preset id (walk/run/idle/jump/...). When set, the pose math is driven by workflow/motions/<id>.json instead of the built-in functions.")
    parser.add_argument("--ik", action="store_true", help="Apply two-bone IK leg solve (motion engine only).")
    parser.add_argument("--fps", type=int, default=8, help="GIF frame rate (motion engine only).")
    for name in ("head_scale", "neck_length", "torso_length", "shoulder_width",
                 "upper_arm_length", "forearm_length", "thigh_length", "shin_length"):
        parser.add_argument(f"--proportion-{name.replace('_', '-')}", type=float,
                            help=f"Body proportion {name} (1.0 = reference base).")
    args = parser.parse_args()

    if args.view == "back" and args.stage in ("pelvis", "arms"):
        raise SystemExit(f"back has no {args.stage} stage yet")

    output = args.output
    output.mkdir(parents=True, exist_ok=True)

    # Activate selected skeleton
    set_skeleton(args.skeleton)

    # Skeleton base: static render, no motion needed
    if args.stage == "skeleton":
        image = render_frame(args.view, "skeleton", 0, 1.0, 1.0, 1.0)
        out = output / f"{args.view}_base.png"
        image.save(out)
        print(f"SKELETON_RENDER_PASS output={out.resolve()}")
        return 0

    # Animated stages: always use data-driven motion engine
    # Default to "walk" if no motion specified
    motion_id = args.motion or "walk"
    from motion import MotionError, PROPORTION_NAMES, load_motion, render_to_output, set_skeleton as motion_set_skeleton
    motion_set_skeleton(args.skeleton)
    motion = load_motion(motion_id)
    overrides = {}
    if args.stride != 1.0: overrides["stride"] = args.stride
    if args.pelvis_bob != 1.0: overrides["pelvis_bob"] = args.pelvis_bob
    if args.arm_swing != 1.0: overrides["arm_swing"] = args.arm_swing
    proportions = {}
    for name in PROPORTION_NAMES:
        value = getattr(args, f"proportion_{name}", None)
        if value is not None:
            proportions[name] = value
    try:
        render_to_output(motion, args.view, args.stage, output,
                         params=overrides or None, use_ik=args.ik, fps=args.fps,
                         proportions=proportions or None)
    except MotionError as error:
        raise SystemExit(f"motion render failed: {error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
