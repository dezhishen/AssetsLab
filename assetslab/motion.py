#!/usr/bin/env python3
"""Data-driven motion engine for AssetsLab skeleton previews.

Motion presets (workflow/motions/<id>.json) describe, in pure data, how each
joint moves over an N-frame cycle.  A preset defines:

  * ``params``   - tunable knobs (stride / pelvis_bob / arm_swing / ...)
  * ``signals``  - named waveform expressions (sine / cosine / phase-table /
                   rectified / negated / combinations)
  * ``offsets``  - per-view, per-stage joint offsets relative to skeleton joints
  * ``selectors``- per-frame limb tags (which leg is in front / foreground)
  * ``ik``       - optional two-bone IK groups (keeps leg lengths constant)

Skeletons are defined in assetslab/presets/<id>.json (v3 preset format).
Species templates are in assetslab/species/<id>.json.
Adding a new skeleton = adding one JSON file; adding a new motion = adding one JSON file.
This is the industry-standard "pose library + procedural sampler" pattern.

CLI
---
    python -m assetslab.motion list
    python -m assetslab.motion info <id>
    python -m assetslab.motion render <id> --view front --stage legs [--skeleton female] [params]
    python -m assetslab.motion check
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]  # repo root
PKG_ROOT = Path(__file__).resolve().parent   # assetslab/
MOTIONS_ROOT = PKG_ROOT / "motions"
PRESETS_ROOT = PKG_ROOT / "presets"
SPECIES_ROOT = PKG_ROOT / "species"
SKELETONS_ROOT = PKG_ROOT / "presets"  # primary lookup

from assetslab.render import (  # noqa: E402
    FRAME_COUNT,
    PREFIX,
    canvas,
    contact_sheet,
    draw_back_legs,
    draw_front_arms,
    draw_front_legs,
    draw_side_arms,
    draw_side_legs,
    make_gif,
    render_back_skeleton,
    render_front_skeleton,
    render_side_base,
)

VIEWS = ("front", "side", "back")
STAGES = ("skeleton", "legs", "pelvis", "arms")
STAGE_ORDER = ("legs", "pelvis", "arms")  # cumulative layers applied for a stage
FLOOR_Y = 470.0


class MotionError(Exception):
    """Raised for invalid motion data or expressions."""


# -- 物种模块注入 ---------------------------------------------------------
# 动作属于物种，因此通过注入的物种模块加载动作（依赖接口，不依赖实现）。
# 未注入时回退到直接文件扫描（兼容旧用法）。

_species_module = None  # 实现了 SpeciesModule 接口的对象（由 server 组装时注入）


def set_species_module(module) -> None:
    """注入物种模块，用于通过其接口加载动作。"""
    global _species_module
    _species_module = module


def _first_preset() -> str:
    """数据驱动默认预设：presets 目录第一个可用（不硬编码具体 id）。"""
    if PRESETS_ROOT.is_dir():
        for p in sorted(PRESETS_ROOT.glob("*.json")):
            if p.name.endswith(".json"):
                return p.stem
    return "standard"


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


def _find_template_file(template_id: str) -> Path | None:
    """Find a species skeleton file: species/<id>/skeleton.json"""
    p = SPECIES_ROOT / template_id / "skeleton.json"
    if p.exists():
        return p
    # backward compat
    for d in [SPECIES_ROOT, SKELETONS_ROOT]:
        p = d / f"{template_id}.json"
        if p.exists():
            return p
    return None


def _find_motion_file(motion_id: str) -> Path | None:
    """Find a motion file: species/*/actions/<id>.json or motions/<id>.json"""
    # Prefer injected species module (动作属于物种，通过接口加载)
    if _species_module is not None and _species_module.find_action(motion_id) is not None:
        return Path("__species__")  # 哨兵：load_motion 走 find_action 分支
    # Search species action dirs directly
    if SPECIES_ROOT.is_dir():
        for sp_dir in SPECIES_ROOT.iterdir():
            if not sp_dir.is_dir():
                continue
            p = sp_dir / "actions" / f"{motion_id}.json"
            if p.exists():
                return p
    # Fallback: legacy motions/ dir
    p = MOTIONS_ROOT / f"{motion_id}.json"
    if p.exists():
        return p
    return None


def load_skeleton(skeleton_id: str = "standard") -> dict:
    """Load skeleton from assetslab/presets/<id>.json.

    Supports:
    - v3 preset: {preset_id, species, positions, body, head_radius}
      → loads referenced species template, merges positions+bones+chains
    - v2/v3 full skeleton: {skeleton_id, views, bones, body, ...}
      → uses directly (backward compatible)
    - Species file: {species_id, joints, bones, chains, ...}
      → structural only, no positions

    Falls back to workflow/motions/base.json for ancient format.
    """
    skel_path = _find_skeleton_file(skeleton_id)
    if skel_path is None:
        # Fallback: old base.json
        base_path = MOTIONS_ROOT / "base.json"
        if skeleton_id == "standard" and base_path.exists():
            data = json.loads(base_path.read_text(encoding="utf-8"))
            return {
                "skeleton_id": "standard", "schema": "assetslab_skeleton_v1",
                "views": data.get("views", {}), "torso": data.get("torso", {}),
                "body": {}, "head_radius": 36, "bones": {},
            }
        raise MotionError(f"skeleton not found: {skeleton_id}")

    data = json.loads(skel_path.read_text(encoding="utf-8"))

    # v3 preset format: references a species template
    species_ref = data.get("species") or data.get("skeleton")
    if species_ref and "positions" in data and "preset_id" in data:
        template_id = species_ref
        template_path = _find_template_file(template_id)
        if template_path is None:
            raise MotionError(f"species template not found: {template_id}")
        template = json.loads(template_path.read_text(encoding="utf-8"))

        # Merge: template provides bones/joints/chains, preset provides positions/proportions
        views = data["positions"]
        # Apply aliases from template (left_hand → palm_left, etc.)
        aliases = template.get("joints", {}).get("aliases", {})
        for view_name in list(views.keys()):
            v = views[view_name]
            for alias, target in aliases.items():
                if target in v and alias not in v:
                    v[alias] = v[target][:]  # copy

        # Build torso inheritance from template's torso_joints
        torso_joints = template.get("torso_joints", [])
        torso = {}
        for view_name in views:
            torso[view_name] = {}
            for j in torso_joints:
                if j in views[view_name]:
                    torso[view_name][j] = 1.0
            # 所有髋关节跟随根运动（front/side/back 各视图的 hip 命名不同，
            # 统一按 "hip" 匹配，否则根运动只带动 front 髋而 pelvis→hip 会拉伸）
            # 同样 rib / clavicle / shoulder 也随躯干刚性运动，避免 chest→rib、
            # sternum→clavicle、clavicle→shoulder 在根起伏/前倾时被拉长。
            for j in views[view_name]:
                if ("hip" in j or "rib" in j or "clavicle" in j or "shoulder" in j):
                    torso[view_name][j] = 1.0
            # Damped joints
            for j in views[view_name]:
                if "knee" in j:
                    torso[view_name][j] = 0.5
            # 头随躯干刚性运动（与 jaw/neck 一致），避免 root 起伏时 head→jaw 撕裂
            torso[view_name]["head"] = 1.0

        # Build upper_joints from template
        upper_joints = {}
        upper_list = template.get("upper_joints", [])
        for view_name in views:
            upper_joints[view_name] = [j for j in upper_list if j in views.get(view_name, {})]

        # Build arm/leg chains from template chains
        arm_chains = {}
        leg_chains = {}
        chains = template.get("chains", {})
        # arm_left chain
        arm_left = chains.get("arm_left", [])
        arm_right = chains.get("arm_right", [])
        leg_left = chains.get("leg_left", [])
        leg_right = chains.get("leg_right", [])
        if arm_left and len(arm_left) >= 2:
            arm_chains["front"] = {
                arm_left[0]: arm_left[1:],
                arm_right[0]: arm_right[1:],
            }
        if leg_left and len(leg_left) >= 2:
            leg_chains["front"] = {
                leg_left[0]: leg_left[1:],
                leg_right[0]: leg_right[1:],
            }

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
            # 物种的物理/解剖学硬约束（含 IK 弯曲方向偏好），随物种同步定义
            "constraints": template.get("constraints", {}),
        }

    # v2/v3 full skeleton format (backward compatible)
    return data


def skeleton_views(skeleton: dict) -> dict:
    """Return {view: {joint_name: (x, y)}} as tuples for vector math."""
    return {view: {name: (float(x), float(y)) for name, (x, y) in joints.items()}
            for view, joints in skeleton.get("views", {}).items()}


def skeleton_body(skeleton: dict) -> dict[str, float]:
    """Return default body proportions from skeleton definition."""
    return dict(skeleton.get("body", {}))


def skeleton_torso(skeleton: dict) -> dict[str, dict[str, float]]:
    """Return torso inheritance weights."""
    return skeleton.get("torso", {})


# Global defaults (used by existing code, reloaded per skeleton)
_BASE_SKELETON: dict | None = None
BASE: dict = {}
TORSO: dict[str, dict[str, float]] = {}
_ARM_CHAINS: dict = {}
_LEG_CHAINS: dict = {}
_UPPER_JOINTS: dict = {}
_ALIASES: dict[str, str] = {}
PROPORTION_NAMES = ("head_scale", "neck_length", "upper_torso_length", "lower_torso_length",
                    "shoulder_width", "upper_arm_length", "forearm_length",
                    "thigh_length", "shin_length")
HEAD_R = 36.0
ROOT_MIN_STAGE = "pelvis"


# 刚性链（脚掌/手掌）从物种 constraints.rigid_chains（3D 规范名）数据驱动生成，
# 不再硬编码任何关节名。ankle 移动 → heel/foot/toe 刚性跟随；wrist → palm/finger。


def _side_view_name(joint: str) -> str:
    """3D 规范名 → side 视图名：左肢→front_<base>、右肢→rear_<base>、躯干同名。"""
    if joint.endswith("_left"):
        return "front_" + joint[:-5]
    if joint.endswith("_right"):
        return "rear_" + joint[:-6]
    return joint


def _back_view_name(joint: str) -> str:
    """3D 规范名 → back 视图名：rear_<原>（左右保留）。"""
    if joint.endswith("_left") or joint.endswith("_right"):
        return "rear_" + joint
    return joint


def _rigid_view_groups() -> dict[str, list[tuple[list[str], list[str]]]]:
    """从物种 constraints.rigid_chains 生成 2D 各视图刚性组（数据驱动）。"""
    sk = _BASE_SKELETON or {}
    chains = (sk.get("constraints", {}).get("rigid_chains", {}).get("chains", []))
    groups: dict[str, list[tuple[list[str], list[str]]]] = {v: [] for v in VIEWS}
    for c in chains:
        driver, follow = c["driver"], c.get("follow", [])
        for view in VIEWS:
            if view == "front":
                groups[view].append(([driver], list(follow)))
            elif view == "side":
                groups[view].append(([_side_view_name(driver)],
                                     [_side_view_name(f) for f in follow]))
            else:
                groups[view].append(([_back_view_name(driver)],
                                     [_back_view_name(f) for f in follow]))
    return groups


def _propagate_rigid(coords: dict, view: str, groups: dict, offset_joints: set | None = None) -> None:
    """刚性链传播（幂等）：跟随关节 = 基准 + 驱动关节位移。

    用*绝对定位*，因此 IK 之后再调用也不会叠加。若跟随关节自带显式偏移则跳过。
    """
    offset_joints = offset_joints or set()
    base = BASE.get(view, {})
    for drivers, followers in groups.get(view, []):
        dx = dy = 0.0
        moved = False
        for dj in drivers:
            if dj not in coords or dj not in base:
                continue
            dx = coords[dj][0] - base[dj][0]
            dy = coords[dj][1] - base[dj][1]
            if dx != 0.0 or dy != 0.0:
                moved = True
                break
        if not moved:
            continue
        for f in followers:
            if f in offset_joints:
                continue
            if f in coords and f in base:
                coords[f] = (base[f][0] + dx, base[f][1] + dy)


def _propagate_foot(coords: dict, view: str, offset_joints: set | None = None) -> None:
    """刚性传播（脚掌/手掌）：驱动关节（ankle/wrist）位移同步给跟随关节。"""
    _propagate_rigid(coords, view, _rigid_view_groups(), offset_joints)


def _propagate_hand(coords: dict, view: str, offset_joints: set | None = None) -> None:
    """刚性传播（幂等，同 _propagate_foot，统一数据驱动刚性链）。"""
    _propagate_rigid(coords, view, _rigid_view_groups(), offset_joints)


def _collect_offset_joints(motion: dict, view: str, stage: str) -> set[str]:
    """收集本帧所有显式偏移关节（含别名↔规范名），供脚部传播跳过自带偏移的关节。"""
    offset_joints: set[str] = set()
    if stage == "skeleton":
        return offset_joints
    for layer in STAGE_ORDER:
        for joint in motion.get("offsets", {}).get(view, {}).get(layer, {}):
            offset_joints.add(joint)
            other = _ALIASES.get(joint)
            if other:
                offset_joints.add(other)
            for alias, canonical in _ALIASES.items():
                if canonical == joint:
                    offset_joints.add(alias)
        if layer == stage:
            break
    return offset_joints


def set_skeleton(skeleton_id: str = "standard") -> dict:
    """Load and activate a skeleton, updating all global references."""
    global _BASE_SKELETON, BASE, TORSO, _ARM_CHAINS, _LEG_CHAINS, _UPPER_JOINTS, HEAD_R, _ALIASES
    _BASE_SKELETON = load_skeleton(skeleton_id)
    BASE = skeleton_views(_BASE_SKELETON)
    TORSO = skeleton_torso(_BASE_SKELETON)
    _ARM_CHAINS = _BASE_SKELETON.get("arm_chains", {})
    _LEG_CHAINS = _BASE_SKELETON.get("leg_chains", {})
    _UPPER_JOINTS = _BASE_SKELETON.get("upper_joints", {})
    _ALIASES = _BASE_SKELETON.get("joints", {}).get("aliases", {})
    HEAD_R = float(_BASE_SKELETON.get("head_radius", 24))
    return _BASE_SKELETON


# Initialize with first available preset (data-driven; engine defers actual load if none)
try:
    set_skeleton(_first_preset())
except Exception:
    _BASE_SKELETON = None


# Legacy compatibility
def load_base() -> dict:
    """Legacy: load base.json joint positions (kept for backward compat)."""
    return BASE.copy()

def apply_proportions(coords: dict, proportions: dict | None, view: str) -> None:
    """Scale bone segments on the static base in place (all factors default 1.0)."""
    p = {name: 1.0 for name in PROPORTION_NAMES}
    for name, value in (proportions or {}).items():
        if name in p and value is not None:
            p[name] = float(value)

    # 1. Torso length — neck/head/shoulders/arms ride up from the pelvis.
    #    With the segmented torso, torso_length still scales the whole neck→pelvis distance.
    if p.get("torso_length", 1.0) != 1.0 and "neck" in coords and "pelvis" in coords:
        dy = (coords["neck"][1] - coords["pelvis"][1]) * (p["torso_length"] - 1.0)
        for name in _UPPER_JOINTS.get(view, []):
            if name in coords:
                coords[name][1] += dy
    # 1b. Upper torso length (neck→waist) — scales bust/chest area, anchored at waist.
    #     上躯干变长 → waist 以上（含胸骨/上胸/锁骨/肩/肋骨/手臂/头）整体上移，
    #     保证脊柱各段（neck/upper_chest/chest/sternum）联动。
    if p.get("upper_torso_length", 1.0) != 1.0 and "neck" in coords and "waist" in coords:
        dy = (coords["neck"][1] - coords["waist"][1]) * (p["upper_torso_length"] - 1.0)
        for name in _UPPER_JOINTS.get(view, []):
            # 排除锚点 waist 和下躯干 abdomen（它们属于 lower_torso）
            if name in ("waist", "abdomen"):
                continue
            if name in coords:
                coords[name][1] += dy
    # 1c. Lower torso length (waist→pelvis) — scales abdomen, anchored at pelvis.
    if p.get("lower_torso_length", 1.0) != 1.0 and "waist" in coords and "pelvis" in coords:
        dy = (coords["waist"][1] - coords["pelvis"][1]) * (p["lower_torso_length"] - 1.0)
        for name in _UPPER_JOINTS.get(view, []):
            if name in coords:
                coords[name][1] += dy
    # 2. Neck length — head rides from the neck (neck segment length).
    if p["neck_length"] != 1.0 and "neck" in coords and "head" in coords:
        nx, ny = coords["neck"]
        hx, hy = coords["head"]
        coords["head"] = [nx + (hx - nx) * p["neck_length"], ny + (hy - ny) * p["neck_length"]]
    # 3. Head scale — scale the head disc BOTTOM-ANCHORED at the neck:
    #    a bigger head grows UPWARD from the chin; the chin→neck gap is owned
    #    solely by neck_length. This keeps head size and neck length independent
    #    (fixes “bigger head → absurdly long neck” when head_scale ≫ 1, e.g. chibi).
    if p["head_scale"] != 1.0 and "head" in coords:
        hx, hy = coords["head"]
        coords["head"] = [hx, hy - HEAD_R * (p["head_scale"] - 1.0)]
    # 4. Shoulder width — spread shoulders around the spine centre; elbows/hands follow.
    if p["shoulder_width"] != 1.0 and "pelvis" in coords:
        cx = coords["pelvis"][0]
        for sh, children in _ARM_CHAINS.get(view, {}).items():
            if sh not in coords:
                continue
            old_x = coords[sh][0]
            coords[sh][0] = cx + (old_x - cx) * p["shoulder_width"]
            dx = coords[sh][0] - old_x
            for child in children:
                if child in coords:
                    coords[child][0] += dx
    # 5. Upper arm length — elbows extend from the shoulders.
    if p["upper_arm_length"] != 1.0:
        for sh, children in _ARM_CHAINS.get(view, {}).items():
            if sh not in coords:
                continue
            sx, sy = coords[sh]
            for c in children:
                if "elbow" in c and c in coords:
                    cx, cy = coords[c]
                    coords[c] = [sx + (cx - sx) * p["upper_arm_length"], sy + (cy - sy) * p["upper_arm_length"]]
    # 6. Forearm length — hands extend from the elbows.
    if p["forearm_length"] != 1.0:
        for sh, children in _ARM_CHAINS.get(view, {}).items():
            elbow = next((coords[c] for c in children if "elbow" in c and c in coords), None)
            if elbow is None:
                continue
            ex, ey = elbow
            for c in children:
                if "hand" in c and c in coords:
                    cx, cy = coords[c]
                    coords[c] = [ex + (cx - ex) * p["forearm_length"], ey + (cy - ey) * p["forearm_length"]]
    # 7+8. Thigh + shin length — COORDINATED: thigh scales the knee from the hip;
    #      shin scales the FOOT from the new knee along the ORIGINAL shin direction.
    #      Feet come up when legs shorten (character shorter — chibi). 
    #      OLD code moved the SAME knee first from the hip then from the foot, so
    #      thigh_length and shin_length cancelled each other and limb length did
    #      nothing (e.g. chibi thigh_length=0.5 still had a 72px thigh).
    if p["thigh_length"] != 1.0 or p["shin_length"] != 1.0:
        for hip_name, chain in _LEG_CHAINS.get(view, {}).items():
            hip = coords.get(hip_name)
            if hip is None:
                continue
            old_knee = next((coords[k] for k in chain if "knee" in k and k in coords), None)
            old_foot = next((coords[f] for f in chain if "foot" in f and f in coords), None)
            if old_knee is None or old_foot is None:
                continue
            # 大腿：膝盖从髋缩放（保持髋→膝方向）
            kx, ky = old_knee
            new_knee = [hip[0] + (kx - hip[0]) * p["thigh_length"],
                        hip[1] + (ky - hip[1]) * p["thigh_length"]]
            # 小腿：脚从新膝盖沿原小腿方向缩放（脚上移=角色变矮）
            sx_, sy_ = old_foot[0] - old_knee[0], old_foot[1] - old_knee[1]
            new_foot = [new_knee[0] + sx_ * p["shin_length"],
                        new_knee[1] + sy_ * p["shin_length"]]
            for k in chain:
                if "knee" in k and k in coords:
                    coords[k] = list(new_knee)
                elif "foot" in k and k in coords:
                    coords[k] = list(new_foot)


# ------------------------------------------------------------ expressions --


def _eval(expr, ctx: dict):
    """Evaluate a motion expression against a context dict.

    ``ctx`` keys: params, index, frame_count, phase, signals (name -> fn(ctx)).
    """
    if isinstance(expr, bool):
        return 1.0 if expr else 0.0
    if isinstance(expr, (int, float)):
        return float(expr)
    if isinstance(expr, str):
        return ctx["signals"][expr](ctx)
    if isinstance(expr, dict):
        if len(expr) != 1:
            raise MotionError(f"expression must be a single-op dict: {expr!r}")
        op, arg = next(iter(expr.items()))
        if op == "param":
            return float(ctx["params"][arg])
        if op == "phase":
            return ctx["phase"]
        if op == "index":
            return float(ctx["index"])
        if op == "frame_count":
            return float(ctx["frame_count"])
        if op == "const":
            return float(arg)
        if op == "signal":
            return ctx["signals"][arg](ctx)
        if op == "sin":
            return math.sin(_eval(arg, ctx))
        if op == "cos":
            return math.cos(_eval(arg, ctx))
        if op == "neg":
            return -_eval(arg, ctx)
        if op == "rect":
            return max(0.0, _eval(arg, ctx))
        if op == "abs":
            return abs(_eval(arg, ctx))
        if op == "add":
            return sum(_eval(a, ctx) for a in arg)
        if op == "sub":
            return _eval(arg[0], ctx) - _eval(arg[1], ctx)
        if op == "mul":
            out = 1.0
            for a in arg:
                out *= _eval(a, ctx)
            return out
        if op == "table":
            return float(arg[ctx["index"] % len(arg)])
        raise MotionError(f"unknown expression op: {op!r}")
    raise MotionError(f"cannot evaluate: {expr!r}")


def _build_signals(motion: dict) -> dict:
    """Return {signal_name: fn(ctx)} for every named signal in the preset."""
    defined = motion.get("signals", {})
    return {name: (lambda expr: (lambda c: _eval(expr, c)))(expr)
            for name, expr in defined.items()}


def _resolve_params(motion: dict, overrides: dict) -> dict:
    defaults = {name: spec.get("default", 0.0)
                for name, spec in motion.get("params", {}).items()}
    merged = dict(defaults)
    for key, value in (overrides or {}).items():
        if key in defaults or key in ("stride", "pelvis_bob", "arm_swing"):
            merged[key] = float(value)
        else:
            raise MotionError(f"unknown motion param: {key}")
    return merged


def _selector_value(motion: dict, name: str, index: int):
    expr = motion.get("selectors", {}).get(name)
    if expr is None:
        return None
    if "table" in expr:
        vals = expr["table"]
        return vals[index % len(vals)]
    if "const" in expr:
        return expr["const"]
    raise MotionError(f"unsupported selector expr: {expr!r}")


# ------------------------------------------------------------------- pose --


def pose(motion: dict, view: str, stage: str, index: int,
         params: dict | None = None, proportions: dict | None = None) -> dict:
    """Sample a full joint dict (name -> (x, y)) plus selectors for a frame.

    The cumulative STAGE_ORDER layers are applied on top of the static base,
    matching the staged render (skeleton -> legs -> pelvis -> arms).  Body
    proportions are applied to the base first (default 1.0 = reference base).
    """
    if view not in BASE:
        raise MotionError(f"unknown view: {view}")
    if stage not in STAGES:
        raise MotionError(f"unknown stage: {stage}")
    params = _resolve_params(motion, params)
    signals = _build_signals(motion)
    frame_count = int(motion.get("frame_count", FRAME_COUNT))
    ctx = {"params": params, "index": index, "frame_count": frame_count,
           "phase": math.tau * float(index % frame_count) / float(frame_count),
           "signals": signals}

    coords = {name: [x, y] for name, (x, y) in BASE[view].items()}
    apply_proportions(coords, proportions, view)
    # 收集本帧所有显式偏移关节（含别名↔规范名），供脚部传播跳过自带偏移的关节。
    offset_joints = _collect_offset_joints(motion, view, stage)
    if stage != "skeleton":
        for layer in STAGE_ORDER:
            layer_offsets = motion.get("offsets", {}).get(view, {}).get(layer, {})
            layer_joints = set(layer_offsets.keys())
            for joint, comp in layer_offsets.items():
                off_x = _eval(comp.get("x", 0.0), ctx)
                off_y = _eval(comp.get("y", 0.0), ctx)
                # 主关节：总是应用（允许创建新关节）
                target = coords.setdefault(joint, [0.0, 0.0])
                target[0] += off_x
                target[1] += off_y
                # 别名同步：仅当别名/规范名不是本层的显式偏移键时交叉应用，
                # 否则会双重叠加（walk 同时有 left_foot 和 foot_left）。
                other = _ALIASES.get(joint)
                if other and other not in layer_joints and other in coords:
                    coords[other][0] += off_x
                    coords[other][1] += off_y
                for alias, canonical in _ALIASES.items():
                    if canonical == joint and alias not in layer_joints and alias in coords:
                        coords[alias][0] += off_x
                        coords[alias][1] += off_y
            if layer == stage:
                break

    # Root motion: rigid-torso transmission (industry root-driven animation).
    # The preset's "root" (pelvis translate) is inherited by every torso joint
    # at its declared ratio, so shoulders/arms/head follow the pelvis instead of
    # requiring per-joint patches.
    root = motion.get("root")
    if root and stage in STAGE_ORDER[STAGE_ORDER.index(ROOT_MIN_STAGE):]:
        dx = _eval(root.get("dx", 0.0), ctx)
        dy = _eval(root.get("dy", 0.0), ctx)
        for joint, inherit in (TORSO.get(view) or {}).items():
            target = coords.get(joint)
            if target is None:
                continue
            target[0] += dx * inherit
            target[1] += dy * inherit

    # 脚部链传播：ankle/heel/toe 与 foot 是刚性脚掌，foot 抬起时它们必须跟随，
    # 否则脚后跟/脚趾钉在地面（"脚掌被吸住"）或踝部脱离（run/jump 的固定关节）。
    _propagate_foot(coords, view, offset_joints)
    # 手部链传播：palm/finger 跟随 wrist（前臂末端）。
    _propagate_hand(coords, view, offset_joints)

    result = {name: (x, y) for name, (x, y) in coords.items()}
    for sel_name in ("front_leg", "foreground_leg", "foreground"):
        value = _selector_value(motion, sel_name, index)
        if value is not None:
            result[sel_name] = value
    return result


# -------------------------------------------------------------- two-bone IK --


def _leg_lengths(view: str, hip: str, knee: str, foot: str) -> tuple[float, float]:
    base = BASE[view]
    dx1 = base[knee][0] - base[hip][0]
    dy1 = base[knee][1] - base[hip][1]
    dx2 = base[foot][0] - base[knee][0]
    dy2 = base[foot][1] - base[knee][1]
    return math.hypot(dx1, dy1), math.hypot(dx2, dy2)


def _arm_lengths(view: str, shoulder: str, elbow: str, hand: str) -> tuple[float, float]:
    base = BASE[view]
    dx1 = base[elbow][0] - base[shoulder][0]
    dy1 = base[elbow][1] - base[shoulder][1]
    dx2 = base[hand][0] - base[elbow][0]
    dy2 = base[hand][1] - base[elbow][1]
    return math.hypot(dx1, dy1), math.hypot(dx2, dy2)


def _rest_side(view: str, hip_name: str, knee_name: str, foot_name: str) -> float:
    """Knee bend direction (+1/-1) fixed by the STATIC rest pose.

    Using the base skeleton keeps the sign stable frame-to-frame.  If we
    recomputed it from the animated knee_ref, a limb that is near-collinear with
    the hip->foot axis (very common: legs move mostly vertically) would flip the
    sign between frames -> the classic IK "knee pop" (knee teleports to the
    other side of the leg).
    """
    base = BASE.get(view, {})
    if not all(n in base for n in (hip_name, knee_name, foot_name)):
        return 1.0
    hx, hy = base[hip_name]
    kx, ky = base[knee_name]
    fx, fy = base[foot_name]
    dx, dy = fx - hx, fy - hy
    dist = math.hypot(dx, dy)
    if dist < 1e-6:
        return 1.0
    ux, uy = dx / dist, dy / dist
    rx, ry = kx - hx, ky - hy
    return 1.0 if (ux * ry - uy * rx) >= 0.0 else -1.0


def ik_solve(hip, foot, knee_ref, l1: float, l2: float, side: float | None = None):
    """Two-bone IK: place knee so hip-knee and knee-foot lengths stay l1/l2.

    ``side`` fixes which side of the hip->foot axis the knee bends (+1/-1).
    When None it is derived from ``knee_ref`` (unstable for near-straight
    limbs — prefer passing ``_rest_side``).
    """
    ax, ay = hip
    cx, cy = foot
    dx, dy = cx - ax, cy - ay
    dist = math.hypot(dx, dy)
    if dist <= 1e-6:
        return (ax, ay - l1)
    ux, uy = dx / dist, dy / dist
    if dist >= l1 + l2:                       # stretched -> straight line
        return (ax + ux * l1, ay + uy * l1)
    if dist <= abs(l1 - l2):                  # folded -> collapse toward foot
        t = max(l1, l2) - min(l1, l2)
        return (ax + ux * t, ay + uy * t)
    cos_a = (l1 * l1 + dist * dist - l2 * l2) / (2.0 * l1 * dist)
    sin_a = math.sqrt(max(0.0, 1.0 - cos_a * cos_a))
    px, py = -uy, ux                              # perpendicular to hip->foot
    if side is None:
        ref = (knee_ref[0] - ax, knee_ref[1] - ay)
        side = 1.0 if (ux * ref[1] - uy * ref[0]) >= 0.0 else -1.0
    return (ax + l1 * (ux * cos_a + side * px * sin_a),
            ay + l1 * (uy * cos_a + side * py * sin_a))


def _bend_sign(mid_name: str, bend: str) -> float:
    """物种约束里的解剖弯曲方向 → ik_solve 的 side 符号。

    forward  (朝前)  -> -1    (膝盖，side 视图 -p 侧 = +x)
    backward (朝后)  -> +1    (肘部，side 视图 +p 侧 = -x)
    outward  (朝外)  -> 左肢 +1 / 右肢 -1 (front 视图肘部)
    """
    if bend == "forward":
        return -1.0
    if bend == "backward":
        return 1.0
    if bend == "outward":
        return 1.0 if "left" in mid_name else -1.0
    return 0.0


def _ik_bend_side(view: str, root_name: str, mid_name: str, tip_name: str,
                  constraints: dict | None) -> float | None:
    """从物种 constraints.joint_direction 查该 IK 链的弯曲方向 → side 符号。
    未定义则返回 None（由调用方回退 _rest_side）。
    """
    for rule in (constraints or {}).get("joint_direction", []):
        if (rule.get("view") == view and rule.get("root") == root_name
                and rule.get("mid") == mid_name and rule.get("tip") == tip_name):
            return _bend_sign(mid_name, rule.get("bend", "forward"))
    return None


def apply_ik(motion: dict, view: str, stage: str, coords: dict,
             clamp_foot: bool = True) -> None:
    """Post-process leg joints with two-bone IK if the preset declares groups.

    The leg groups are declared once under ``ik[view]["legs"]`` and applied to
    any stage that renders legs (legs/pelvis/arms), so the limb keeps its
    rest-pose length even at extreme stride values.  IK bend direction is read
    from the species ``constraints.joint_direction`` (data-driven), falling back
    to the static rest pose when undefined — the engine itself is generic.

    ``clamp_foot`` is the industry "foot plant" behaviour: when the data-driven
    foot target is beyond the hip->knee + knee->foot reach, the foot is locked
    back onto the reachable radius so the limb never hyper-extends (it slides
    along the ground instead of stretching).
    """
    if stage == "skeleton":
        return
    constraints = (_BASE_SKELETON or {}).get("constraints", {}) if _BASE_SKELETON else {}
    ik = motion.get("ik", {}).get(view, {})
    # ---- legs: 两骨 IK，末端 = ankle（小腿 knee→ankle 才是真腿段）----
    for leg, group in ik.get("legs", {}).items():
        hip_name, knee_name, foot_name = group["hip"], group["knee"], group["foot"]
        l1, l2 = _leg_lengths(view, hip_name, knee_name, foot_name)
        hip = coords[hip_name]
        foot = coords[foot_name]
        dx, dy = foot[0] - hip[0], foot[1] - hip[1]
        reach = math.hypot(dx, dy)
        if clamp_foot and reach > l1 + l2 and reach > 1e-6:
            ux, uy = dx / reach, dy / reach
            foot = (hip[0] + ux * (l1 + l2), hip[1] + uy * (l1 + l2))
            coords[foot_name] = foot
        side = _ik_bend_side(view, hip_name, knee_name, foot_name, constraints)
        if side is None:
            side = _rest_side(view, hip_name, knee_name, foot_name)
        knee = ik_solve(hip, foot, coords[knee_name], l1, l2, side)
        coords[knee_name] = knee
    # ---- arms: 两骨 IK，末端 = wrist（前臂 elbow→wrist 才是真臂段）----
    for arm, group in ik.get("arms", {}).items():
        sh_name, el_name, wr_name = group["shoulder"], group["elbow"], group["hand"]
        l1, l2 = _arm_lengths(view, sh_name, el_name, wr_name)
        shoulder = coords[sh_name]
        wrist = coords[wr_name]
        dx, dy = wrist[0] - shoulder[0], wrist[1] - shoulder[1]
        reach = math.hypot(dx, dy)
        # 手臂钳制在弯曲空间内（< 臂长），避免肘部在伸直临界处弹跳（跳侧抽搐）。
        # 因子 arm_bend_factor 由物种 constraints 数据驱动（默认 0.96 = 保留 4% 弯曲）。
        bend = float((constraints or {}).get("arm_bend_factor", 0.96))
        max_reach = (l1 + l2) * bend
        if clamp_foot and reach > max_reach and reach > 1e-6:
            ux, uy = dx / reach, dy / reach
            wrist = (shoulder[0] + ux * max_reach, shoulder[1] + uy * max_reach)
            coords[wr_name] = wrist
        side = _ik_bend_side(view, sh_name, el_name, wr_name, constraints)
        if side is None:
            side = _rest_side(view, sh_name, el_name, wr_name)
        elbow = ik_solve(shoulder, wrist, coords[el_name], l1, l2, side)
        coords[el_name] = elbow


# ----------------------------------------------------------------- render --


def render_frame(motion: dict, view: str, stage: str, index: int,
                 params: dict | None = None, use_ik: bool = False,
                 proportions: dict | None = None):
    """Render one frame as a PIL image (same look as the Godot captures)."""
    base = BASE[view]
    image, draw = canvas()
    if stage == "skeleton":
        # Static skeleton also honours proportions (body shape preview).
        coords = pose(motion, view, "skeleton", 0, params, proportions)
        if view == "front":
            render_front_skeleton(image, draw, coords)
        elif view == "side":
            render_side_base(image, draw, coords)
        else:
            render_back_skeleton(image, draw, coords)
        return image

    coords = pose(motion, view, stage, index, params, proportions)
    if use_ik:
        apply_ik(motion, view, stage, coords)
        # IK 可能钳制末端（腿长/臂长超限）→ 重新把脚掌/手掌附着到最终末端（幂等）
        _oj = _collect_offset_joints(motion, view, stage)
        _propagate_foot(coords, view, _oj)
        _propagate_hand(coords, view, _oj)

    if view == "front":
        if stage == "legs":
            draw_front_legs(image, draw, coords, base)
        elif stage == "pelvis":
            draw_front_legs(image, draw, coords, base)
        else:  # arms
            arms = {k: coords[k] for k in ("left_elbow", "left_hand", "right_elbow", "right_hand")}
            draw_front_arms(image, draw, coords, arms, base)
    elif view == "side":
        if stage == "legs":
            draw_side_legs(image, draw, coords, base)
        elif stage == "pelvis":
            draw_side_legs(image, draw, coords, base)
        else:
            arms = {k: coords[k] for k in ("rear_elbow", "rear_hand", "front_elbow", "front_hand")}
            draw_side_arms(image, draw, coords, arms, base)
    else:  # back
        draw_back_legs(image, draw, coords, base)
    return image


def render_motion(motion: dict, view: str, stage: str,
                  params: dict | None = None, use_ik: bool = False,
                  blend_motion: dict | None = None, blend_t: float = 0.0,
                  proportions: dict | None = None):
    """Return an ordered list of PIL frames for an entire cycle."""
    frame_count = int(motion.get("frame_count", FRAME_COUNT))
    frames = []
    for i in range(frame_count):
        image = render_frame(motion, view, stage, i, params, use_ik, proportions)
        if blend_motion is not None and blend_t > 0.0:
            other = render_frame(blend_motion, view, stage, i, params, use_ik, proportions)
            image = Image.blend(image, other, blend_t)
        frames.append(image)
    return frames


def render_to_output(motion: dict, view: str, stage: str, output: Path,
                     params: dict | None = None, use_ik: bool = False,
                     fps: int = 8, blend_motion: dict | None = None,
                     blend_t: float = 0.0, proportions: dict | None = None) -> None:
    """Render a stage and write PNG/GIF with the same names as the pipeline."""
    output.mkdir(parents=True, exist_ok=True)
    motion_id = motion["motion_id"]
    frames = render_motion(motion, view, stage, params, use_ik, blend_motion, blend_t, proportions)
    if stage == "skeleton":
        out = output / f"{view}_base_{motion_id}.png"
        frames[0].save(out)
        print(f"MOTION_RENDER_PASS motion={motion_id} view={view} stage={stage} output={out.resolve()}")
        return
    prefix = PREFIX.get((view, stage))
    if prefix is None:
        raise MotionError(f"no output prefix for {view} {stage}")
    tag = f"{prefix}_{motion_id}"
    sheet = output / f"{tag}_8frames.png"
    gif = output / f"{tag}.gif"
    contact_sheet(frames, sheet)
    make_gif(frames, gif, duration=int(1000 / max(1, fps)))
    print(f"MOTION_RENDER_PASS motion={motion_id} view={view} stage={stage} frames={len(frames)} sheet={sheet.resolve()}")
    print(f"MOTION_RENDER_GIF={gif.resolve()}")


# ---------------------------------------------------------------- check --


def _builtin_pose(view: str, stage: str, index: int) -> dict:
    """Reference pose from the original built-in functions (walk only)."""
    from render_skeleton_preview import (  # noqa: E402
        back_leg_pose,
        front_arm_pose,
        front_leg_pose,
        front_pelvis_pose,
        side_arm_pose,
        side_leg_pose,
        side_pelvis_pose,
    )
    if view == "front":
        if stage == "legs":
            return front_leg_pose(index)
        if stage == "pelvis":
            return front_pelvis_pose(index)
        if stage == "arms":
            pose_ = dict(front_pelvis_pose(index))
            pose_.update(front_arm_pose(index))
            return pose_
    if view == "side":
        if stage == "legs":
            return side_leg_pose(index)
        if stage == "pelvis":
            return side_pelvis_pose(index)
        if stage == "arms":
            pose_ = dict(side_pelvis_pose(index))
            pose_.update(side_arm_pose(index))
            return pose_
    if view == "back" and stage == "legs":
        return back_leg_pose(index)
    if stage == "skeleton":
        # Static skeleton renders the base pose verbatim.
        return dict(BASE[view])
    raise MotionError(f"no built-in reference for {view} {stage}")


def _joints_to_compare(view: str, stage: str) -> list[str]:
    if stage == "skeleton":
        return list(BASE[view])
    if view == "front":
        legs = ["left_hip", "right_hip", "left_knee", "right_knee", "left_foot", "right_foot"]
        upper = ["shoulder_left", "shoulder_right", "elbow_left", "elbow_right", "hand_left", "hand_right"]
        if stage == "legs":
            return legs
        if stage == "pelvis":
            return legs + ["pelvis", "head", "neck"] + upper
        return legs + ["pelvis", "head", "neck", "left_elbow", "left_hand", "right_elbow", "right_hand"]
    if view == "side":
        legs = ["rear_hip", "front_hip", "rear_knee", "front_knee", "rear_foot", "front_foot"]
        upper = ["rear_shoulder", "front_shoulder", "rear_elbow", "front_elbow", "rear_hand", "front_hand"]
        if stage == "legs":
            return legs
        if stage == "pelvis":
            return legs + ["pelvis", "head", "neck"] + upper
        return legs + ["pelvis", "head", "neck"] + upper
    # back
    return ["left_hip", "right_hip", "left_knee", "right_knee", "left_foot", "right_foot", "head", "neck"]


def check_walk(tolerance: float = 1e-6) -> int:
    """Verify the data-driven walk preset matches the built-in pose functions."""
    motion = load_motion("walk")
    failures: list[str] = []
    for view in VIEWS:
        stages = STAGES if view != "back" else ("skeleton", "legs")
        for stage in stages:
            for index in range(int(motion["frame_count"])):
                data = pose(motion, view, stage, index, {"stride": 1.0, "pelvis_bob": 1.0, "arm_swing": 1.0})
                builtin = _builtin_pose(view, stage, index)
                for joint in _joints_to_compare(view, stage):
                    dp = data[joint]
                    bp = builtin[joint]
                    for axis, (a, b) in enumerate(zip(dp, bp)):
                        if abs(a - b) > tolerance:
                            failures.append(
                                f"{view}/{stage} frame {index} {joint}[{'xy'[axis]}] data={a} builtin={b}")
    if failures:
        print(f"MOTION_CHECK_FAIL ({len(failures)} mismatches)")
        for line in failures[:40]:
            print("  " + line)
        return 1
    print(f"MOTION_CHECK_PASS walk preset matches built-in poses (all views/stages/frames)")
    return 0


# ------------------------------------------------------------------- CLI --


def load_motion(motion_id: str) -> dict:
    # 优先通过注入的物种模块加载（动作属于物种）
    if _species_module is not None:
        found = _species_module.find_action(motion_id)
        if found is not None:
            _species_id, motion = found
            if motion.get("schema") != "assetslab_motion_v1":
                raise MotionError(f"unsupported motion schema: {motion_id}")
            return motion
    path = _find_motion_file(motion_id)
    if path is None or str(path) == "__species__":
        raise MotionError(f"motion not found: {motion_id}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != "assetslab_motion_v1":
        raise MotionError(f"unsupported motion schema in {path}")
    return data


def _all_motions() -> list[dict]:
    items = []
    seen = set()
    # Scan species/*/actions/
    if SPECIES_ROOT.is_dir():
        for sp_dir in sorted(SPECIES_ROOT.iterdir()):
            if not sp_dir.is_dir():
                continue
            actions_dir = sp_dir / "actions"
            if not actions_dir.is_dir():
                continue
            for path in sorted(actions_dir.glob("*.json")):
                if path.name == "base.json":
                    continue
                data = json.loads(path.read_text(encoding="utf-8"))
                mid = data.get("motion_id", path.stem)
                if mid in seen:
                    continue
                seen.add(mid)
                items.append({"motion_id": mid, "title": data.get("title", mid),
                              "params": list(data.get("params", {}).keys()),
                              "has_ik": bool(data.get("ik"))})
    # Fallback: legacy motions/
    if MOTIONS_ROOT.is_dir():
        for path in sorted(MOTIONS_ROOT.glob("*.json")):
            if path.name == "base.json":
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            mid = data.get("motion_id", path.stem)
            if mid in seen:
                continue
            seen.add(mid)
            items.append({"motion_id": mid, "title": data.get("title", mid),
                          "params": list(data.get("params", {}).keys()),
                          "has_ik": bool(data.get("ik"))})
    return items


def cmd_list() -> int:
    for item in _all_motions():
        ik = "  ik" if item["has_ik"] else ""
        print(f"{item['motion_id']:<12} {item['title']}  params={', '.join(item['params'])}{ik}")
    return 0


def cmd_info(motion_id: str) -> int:
    motion = load_motion(motion_id)
    print(f"motion_id : {motion['motion_id']}")
    print(f"title     : {motion.get('title')}")
    print(f"frames    : {motion.get('frame_count')}")
    print(f"ik        : {sorted(motion.get('ik', {}).get('front', {}).get('legs', {})) if motion.get('ik') else 'no'}")
    print("params:")
    for name, spec in motion.get("params", {}).items():
        print(f"  {name:<12} default={spec.get('default')} range=[{spec.get('min')}, {spec.get('max')}] {spec.get('label', '')}")
    if motion.get("description"):
        print(f"notes     : {motion['description']}")
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    # Activate the selected skeleton
    set_skeleton(args.skeleton)
    motion = load_motion(args.motion)
    blend_motion = load_motion(args.blend) if args.blend else None
    overrides = {}
    if args.stride is not None:
        overrides["stride"] = args.stride
    if args.pelvis_bob is not None:
        overrides["pelvis_bob"] = args.pelvis_bob
    if args.arm_swing is not None:
        overrides["arm_swing"] = args.arm_swing
    proportions = {}
    for name in PROPORTION_NAMES:
        value = getattr(args, f"proportion_{name}", None)
        if value is not None:
            proportions[name] = value
    render_to_output(motion, args.view, args.stage, args.output,
                     params=overrides or None, use_ik=args.ik,
                     fps=args.fps, blend_motion=blend_motion, blend_t=args.blend_t,
                     proportions=proportions or None)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Data-driven skeleton motion engine")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List available motion presets.")

    p = sub.add_parser("info", help="Show a motion preset's parameters.")
    p.add_argument("motion")

    p = sub.add_parser("render", help="Render a motion stage to PNG/GIF.")
    p.add_argument("motion", choices=[m["motion_id"] for m in _all_motions()])
    p.add_argument("--skeleton", default="standard", help="Preset id (standard, female, ...) from assetslab/presets/.")
    p.add_argument("--view", choices=list(VIEWS), required=True)
    p.add_argument("--stage", choices=list(STAGES), required=True)
    p.add_argument("--output", type=Path, default=ROOT / "prototype" / "test_output" / "skeleton_pipeline")
    p.add_argument("--stride", type=float)
    p.add_argument("--pelvis-bob", type=float)
    p.add_argument("--arm-swing", type=float)
    for name in PROPORTION_NAMES:
        p.add_argument(f"--proportion-{name.replace('_', '-')}", type=float,
                       help=f"Body proportion {name} (1.0 = reference base).")
    p.add_argument("--fps", type=int, default=8)
    p.add_argument("--ik", action="store_true", help="Apply two-bone IK leg solve if the preset declares groups.")
    p.add_argument("--blend", metavar="MOTION", help="Blend toward another motion by joint interpolation.")
    p.add_argument("--blend-t", type=float, default=0.0, help="Blend factor 0..1 (0 = pure primary).")

    sub.add_parser("check", help="Verify the walk preset matches the built-in poses.")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "list":
        return cmd_list()
    if args.command == "info":
        return cmd_info(args.motion)
    if args.command == "render":
        return cmd_render(args)
    if args.command == "check":
        return check_walk()
    return 2


if __name__ == "__main__":
    sys.exit(main())
