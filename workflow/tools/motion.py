#!/usr/bin/env python3
"""Data-driven motion engine for AssetsLab skeleton previews.

Motion presets (workflow/motions/<id>.json) describe, in pure data, how each
joint moves over an N-frame cycle.  A preset defines:

  * ``params``   - tunable knobs (stride / pelvis_bob / arm_swing / ...)
  * ``signals``  - named waveform expressions (sine / cosine / phase-table /
                   rectified / negated / combinations)
  * ``offsets``  - per-view, per-stage joint offsets relative to base.json
  * ``selectors``- per-frame limb tags (which leg is in front / foreground)
  * ``ik``       - optional two-bone IK groups (keeps leg lengths constant)

This is the industry-standard "pose library + procedural sampler" pattern:
adding a new animation is a new JSON file, no renderer changes.

CLI
---
    python workflow/tools/motion.py list
    python workflow/tools/motion.py info <id>
    python workflow/tools/motion.py render <id> --view front --stage legs [params]
    python workflow/tools/motion.py check          # walk preset == built-in poses
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
MOTIONS_ROOT = ROOT / "workflow" / "motions"

from render_skeleton_preview import (  # noqa: E402  (same directory)
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


# ------------------------------------------------------------------- base --


def load_base() -> dict:
    data = json.loads((MOTIONS_ROOT / "base.json").read_text(encoding="utf-8"))
    views = data["views"]
    # Convert lists to (x, y) tuples for vector math.
    return {view: {name: (float(x), float(y)) for name, (x, y) in joints.items()}
            for view, joints in views.items()}


BASE = load_base()


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
         params: dict | None = None) -> dict:
    """Sample a full joint dict (name -> (x, y)) plus selectors for a frame.

    The cumulative STAGE_ORDER layers are applied on top of the static base,
    matching the staged render (skeleton -> legs -> pelvis -> arms).
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
    if stage != "skeleton":
        for layer in STAGE_ORDER:
            layer_offsets = motion.get("offsets", {}).get(view, {}).get(layer, {})
            for joint, comp in layer_offsets.items():
                off_x = _eval(comp.get("x", 0.0), ctx)
                off_y = _eval(comp.get("y", 0.0), ctx)
                target = coords.setdefault(joint, [0.0, 0.0])
                target[0] += off_x
                target[1] += off_y
            if layer == stage:
                break

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


def ik_solve(hip, foot, knee_ref, l1: float, l2: float):
    """Two-bone IK: place knee so hip-knee and knee-foot lengths stay l1/l2.

    The knee is bent toward the side where the reference knee sits relative to
    the hip->foot axis, which keeps limbs inside the body (no hyper-extension).
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
    ref = (knee_ref[0] - ax, knee_ref[1] - ay)
    side = 1.0 if (ux * ref[1] - uy * ref[0]) >= 0.0 else -1.0
    return (ax + l1 * (ux * cos_a + side * px * sin_a),
            ay + l1 * (uy * cos_a + side * py * sin_a))


def apply_ik(motion: dict, view: str, stage: str, coords: dict,
             clamp_foot: bool = True) -> None:
    """Post-process leg joints with two-bone IK if the preset declares groups.

    The leg groups are declared once under ``ik[view]["legs"]`` and applied to
    any stage that renders legs (legs/pelvis/arms), so the limb keeps its
    rest-pose length even at extreme stride values.

    ``clamp_foot`` is the industry "foot plant" behaviour: when the data-driven
    foot target is beyond the hip->knee + knee->foot reach, the foot is locked
    back onto the reachable radius so the limb never hyper-extends (it slides
    along the ground instead of stretching).
    """
    if stage == "skeleton":
        return
    groups = motion.get("ik", {}).get(view, {}).get("legs", {})
    if not groups:
        return
    for leg, group in groups.items():
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
        knee = ik_solve(hip, foot, coords[knee_name], l1, l2)
        coords[knee_name] = knee


# ----------------------------------------------------------------- render --


def render_frame(motion: dict, view: str, stage: str, index: int,
                 params: dict | None = None, use_ik: bool = False):
    """Render one frame as a PIL image (same look as the Godot captures)."""
    base = BASE[view]
    image, draw = canvas()
    if stage == "skeleton":
        if view == "front":
            render_front_skeleton(image, draw, base)
        elif view == "side":
            render_side_base(image, draw, base)
        else:
            render_back_skeleton(image, draw, base)
        return image

    coords = pose(motion, view, stage, index, params)
    if use_ik:
        apply_ik(motion, view, stage, coords)

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
                  blend_motion: dict | None = None, blend_t: float = 0.0):
    """Return an ordered list of PIL frames for an entire cycle."""
    frame_count = int(motion.get("frame_count", FRAME_COUNT))
    frames = []
    for i in range(frame_count):
        image = render_frame(motion, view, stage, i, params, use_ik)
        if blend_motion is not None and blend_t > 0.0:
            other = render_frame(blend_motion, view, stage, i, params, use_ik)
            image = Image.blend(image, other, blend_t)
        frames.append(image)
    return frames


def render_to_output(motion: dict, view: str, stage: str, output: Path,
                     params: dict | None = None, use_ik: bool = False,
                     fps: int = 8, blend_motion: dict | None = None,
                     blend_t: float = 0.0) -> None:
    """Render a stage and write PNG/GIF with the same names as the pipeline."""
    output.mkdir(parents=True, exist_ok=True)
    motion_id = motion["motion_id"]
    frames = render_motion(motion, view, stage, params, use_ik, blend_motion, blend_t)
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
        if stage == "legs":
            return legs
        if stage == "pelvis":
            return legs + ["pelvis", "head", "neck"]
        return legs + ["pelvis", "head", "neck", "left_elbow", "left_hand", "right_elbow", "right_hand"]
    if view == "side":
        legs = ["rear_hip", "front_hip", "rear_knee", "front_knee", "rear_foot", "front_foot"]
        if stage == "legs":
            return legs
        if stage == "pelvis":
            return legs + ["pelvis", "head", "neck"]
        return legs + ["pelvis", "head", "neck", "rear_elbow", "rear_hand", "front_elbow", "front_hand"]
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
    path = MOTIONS_ROOT / f"{motion_id}.json"
    if not path.exists():
        raise MotionError(f"motion not found: {motion_id} ({path})")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != "assetslab_motion_v1":
        raise MotionError(f"unsupported motion schema in {path}")
    return data


def _all_motions() -> list[dict]:
    items = []
    for path in sorted(MOTIONS_ROOT.glob("*.json")):
        if path.name == "base.json":
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        items.append({"motion_id": data.get("motion_id"), "title": data.get("title"),
                      "params": list(data.get("params", {})), "has_ik": bool(data.get("ik"))})
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
    motion = load_motion(args.motion)
    blend_motion = load_motion(args.blend) if args.blend else None
    overrides = {}
    if args.stride is not None:
        overrides["stride"] = args.stride
    if args.pelvis_bob is not None:
        overrides["pelvis_bob"] = args.pelvis_bob
    if args.arm_swing is not None:
        overrides["arm_swing"] = args.arm_swing
    render_to_output(motion, args.view, args.stage, args.output,
                     params=overrides or None, use_ik=args.ik,
                     fps=args.fps, blend_motion=blend_motion, blend_t=args.blend_t)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Data-driven skeleton motion engine")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List available motion presets.")

    p = sub.add_parser("info", help="Show a motion preset's parameters.")
    p.add_argument("motion")

    p = sub.add_parser("render", help="Render a motion stage to PNG/GIF.")
    p.add_argument("motion", choices=[m["motion_id"] for m in _all_motions()])
    p.add_argument("--view", choices=list(VIEWS), required=True)
    p.add_argument("--stage", choices=list(STAGES), required=True)
    p.add_argument("--output", type=Path, default=ROOT / "prototype" / "test_output" / "skeleton_pipeline")
    p.add_argument("--stride", type=float)
    p.add_argument("--pelvis-bob", type=float)
    p.add_argument("--arm-swing", type=float)
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
