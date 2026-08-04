#!/usr/bin/env python3
"""Render skeleton pipeline previews with Pillow (pure Python, no Godot).

Pose math is ported from the GDScript stage models so the output matches the
Godot headless capture (colors, line widths, anchors).  Parameters let AI or a
human tune the pose directly:

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

ROOT = Path(__file__).resolve().parents[2]
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


def head(draw, center, color=BONE, radius=68, width=4):
    box = (center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius)
    draw.arc(box, 0, 360, fill=color, width=width)


def joint(draw, point, color=JOINT, radius=7):
    box = (point[0] - radius, point[1] - radius, point[0] + radius, point[1] + radius)
    draw.ellipse(box, fill=color, outline=HEAD_DARK, width=2)


def pelvis(draw, point):
    box = (point[0] - 14, point[1] - 14, point[0] + 14, point[1] + 14)
    draw.ellipse(box, fill=PELVIS_C, outline=(77, 43, 32), width=2)


# ------------------------------------------------------------- base points --


def front_base() -> dict:
    return {
        "head": (CENTER_X, 150.0), "neck": (CENTER_X, 238.0),
        "shoulder_left": (422.0, 260.0), "shoulder_right": (538.0, 260.0),
        "elbow_left": (400.0, 325.0), "elbow_right": (560.0, 325.0),
        "hand_left": (392.0, 382.0), "hand_right": (568.0, 382.0),
        "pelvis": (CENTER_X, 350.0),
        "hip_left": (448.0, 356.0), "hip_right": (512.0, 356.0),
        "knee_left": (448.0, 415.0), "knee_right": (512.0, 415.0),
        "foot_left": (448.0, FLOOR_Y), "foot_right": (512.0, FLOOR_Y),
    }


def side_base() -> dict:
    return {
        "head": (ROOT_X, 150.0), "face_forward": (548.0, 150.0), "neck": (ROOT_X, 238.0),
        "pelvis": (ROOT_X, 350.0),
        "rear_shoulder": (462.0, 264.0), "front_shoulder": (498.0, 258.0),
        "rear_elbow": (448.0, 326.0), "front_elbow": (510.0, 320.0),
        "rear_hand": (444.0, 382.0), "front_hand": (518.0, 376.0),
        "rear_hip": (466.0, 356.0), "front_hip": (494.0, 350.0),
        "rear_knee": (462.0, 414.0), "front_knee": (498.0, 410.0),
        "rear_foot": (452.0, FLOOR_Y), "front_foot": (512.0, FLOOR_Y),
    }


def back_base() -> dict:
    return {
        "head": (CENTER_X, 150), "neck": (CENTER_X, 238), "pelvis": (CENTER_X, 350),
        "rear_shoulder_left": (422, 264), "rear_shoulder_right": (538, 264),
        "front_shoulder_left": (432, 258), "front_shoulder_right": (528, 258),
        "rear_elbow_left": (400, 326), "rear_elbow_right": (560, 326),
        "front_elbow_left": (410, 320), "front_elbow_right": (550, 320),
        "rear_hand_left": (392, 382), "rear_hand_right": (568, 382),
        "front_hand_left": (402, 376), "front_hand_right": (558, 376),
        "rear_hip_left": (448, 356), "rear_hip_right": (512, 356),
        "front_hip_left": (456, 350), "front_hip_right": (504, 350),
        "rear_knee_left": (448, 414), "rear_knee_right": (512, 414),
        "front_knee_left": (456, 410), "front_knee_right": (504, 410),
        "rear_foot_left": (448, FLOOR_Y), "rear_foot_right": (512, FLOOR_Y),
        "front_foot_left": (456, FLOOR_Y), "front_foot_right": (504, FLOOR_Y),
    }


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
    for joint in ("pelvis", "rear_hip", "front_hip",
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


def render_front_skeleton(image, draw, base):
    bone(draw, base["head"], base["neck"], BONE)
    bone(draw, base["shoulder_left"], base["shoulder_right"], BONE)
    bone(draw, base["neck"], base["pelvis"], BONE)
    for side in ("left", "right"):
        bone(draw, base[f"shoulder_{side}"], base[f"elbow_{side}"], BONE)
        bone(draw, base[f"elbow_{side}"], base[f"hand_{side}"], BONE)
        bone(draw, base["hip_" + side], base[f"knee_{side}"], BONE)
        bone(draw, base[f"knee_{side}"], base[f"foot_{side}"], BONE)
    bone(draw, base["hip_left"], base["hip_right"], BONE)
    bone(draw, base["pelvis"], base["hip_left"], BONE)
    bone(draw, base["pelvis"], base["hip_right"], BONE)
    head(draw, base["head"])
    for key in base:
        joint(draw, base[key])
    pelvis(draw, base["pelvis"])


def draw_front_legs(image, draw, pose, base):
    pelvis_point = pose.get("pelvis", base["pelvis"])
    head_point = pose.get("head", base["head"])
    neck_point = pose.get("neck", base["neck"])
    shoulder_l = pose.get("shoulder_left", base["shoulder_left"])
    shoulder_r = pose.get("shoulder_right", base["shoulder_right"])
    elbow_l = pose.get("elbow_left", base["elbow_left"])
    elbow_r = pose.get("elbow_right", base["elbow_right"])
    hand_l = pose.get("hand_left", base["hand_left"])
    hand_r = pose.get("hand_right", base["hand_right"])
    bone(draw, head_point, neck_point, BONE)
    bone(draw, shoulder_l, shoulder_r, BONE)
    bone(draw, shoulder_l, elbow_l, BONE)
    bone(draw, shoulder_r, elbow_r, BONE)
    bone(draw, elbow_l, hand_l, BONE)
    bone(draw, elbow_r, hand_r, BONE)
    bone(draw, neck_point, pelvis_point, BONE)
    head(draw, head_point)
    rear = "right" if pose["front_leg"] == "left" else "left"
    for name, color in ((rear, REAR), (pose["front_leg"], FRONT)):
        bone(draw, pose[f"{name}_hip"], pose[f"{name}_knee"], color, 8)
        bone(draw, pose[f"{name}_knee"], pose[f"{name}_foot"], color, 8)
        for key in (f"{name}_hip", f"{name}_knee", f"{name}_foot"):
            joint(draw, pose[key])
    pelvis(draw, pelvis_point)


def draw_front_arms(image, draw, pose, arms, base):
    head_point = pose.get("head", base["head"])
    neck_point = pose.get("neck", base["neck"])
    shoulder_l = pose.get("shoulder_left", base["shoulder_left"])
    shoulder_r = pose.get("shoulder_right", base["shoulder_right"])
    bone(draw, head_point, neck_point, BONE)
    bone(draw, shoulder_l, shoulder_r, BONE)
    bone(draw, neck_point, pose["pelvis"], BONE)
    head(draw, head_point)
    bone(draw, shoulder_l, arms["left_elbow"], ARM, 7)
    bone(draw, arms["left_elbow"], arms["left_hand"], ARM, 7)
    bone(draw, shoulder_r, arms["right_elbow"], ARM, 7)
    bone(draw, arms["right_elbow"], arms["right_hand"], ARM, 7)
    rear = "right" if pose["front_leg"] == "left" else "left"
    for name, color in ((rear, REAR), (pose["front_leg"], FRONT)):
        bone(draw, pose[f"{name}_hip"], pose[f"{name}_knee"], color, 8)
        bone(draw, pose[f"{name}_knee"], pose[f"{name}_foot"], color, 8)
    pelvis(draw, pose["pelvis"])


def render_side_base(image, draw, base):
    bone(draw, base["head"], base["neck"], BONE)
    bone(draw, base["neck"], base["pelvis"], BONE)
    head(draw, base["head"])
    for limb, color in (("rear", REAR), ("front", FRONT)):
        bone(draw, base[f"{limb}_shoulder"], base[f"{limb}_elbow"], color)
        bone(draw, base[f"{limb}_elbow"], base[f"{limb}_hand"], color)
        bone(draw, base["pelvis"], base[f"{limb}_hip"], color)
        bone(draw, base[f"{limb}_hip"], base[f"{limb}_knee"], color)
        bone(draw, base[f"{limb}_knee"], base[f"{limb}_foot"], color)
    for key in base:
        if key != "face_forward":
            joint(draw, base[key])
    pelvis(draw, base["pelvis"])


def draw_side_legs(image, draw, pose, base):
    pelvis_point = pose.get("pelvis", base["pelvis"])
    head_point = pose.get("head", base["head"])
    neck_point = pose.get("neck", base["neck"])
    bone(draw, head_point, neck_point, BONE)
    bone(draw, neck_point, pelvis_point, BONE)
    head(draw, head_point)
    rear_name = "rear" if pose["foreground_leg"] == "front" else "front"
    for name, color in ((rear_name, REAR), (pose["foreground_leg"], FRONT)):
        bone(draw, pose[f"{name}_hip"], pose[f"{name}_knee"], color, 8)
        bone(draw, pose[f"{name}_knee"], pose[f"{name}_foot"], color, 8)
        for key in (f"{name}_hip", f"{name}_knee", f"{name}_foot"):
            joint(draw, pose[key])
    pelvis(draw, pelvis_point)


def draw_side_arms(image, draw, pose, arms, base):
    head_point = pose.get("head", base["head"])
    neck_point = pose.get("neck", base["neck"])
    bone(draw, head_point, neck_point, BONE)
    bone(draw, neck_point, pose["pelvis"], BONE)
    head(draw, head_point)
    for limb, color in (("rear", ARM), ("front", ARM)):
        shoulder = pose.get(f"{limb}_shoulder", base[f"{limb}_shoulder"])
        bone(draw, shoulder, arms[f"{limb}_elbow"], color, 7)
        bone(draw, arms[f"{limb}_elbow"], arms[f"{limb}_hand"], color, 7)
    for name, color in ((pose["foreground_leg"], FRONT), ("rear" if pose["foreground_leg"] == "front" else "front", REAR)):
        bone(draw, pose[f"{name}_hip"], pose[f"{name}_knee"], color, 8)
        bone(draw, pose[f"{name}_knee"], pose[f"{name}_foot"], color, 8)
    pelvis(draw, pose["pelvis"])


def render_back_skeleton(image, draw, base):
    bone(draw, base["head"], base["neck"], BONE)
    bone(draw, base["neck"], base["pelvis"], BONE)
    head(draw, base["head"])
    for limb, color in (("rear", REAR), ("front", FRONT)):
        for side in ("left", "right"):
            bone(draw, base[f"{limb}_shoulder_{side}"], base[f"{limb}_elbow_{side}"], color)
            bone(draw, base[f"{limb}_elbow_{side}"], base[f"{limb}_hand_{side}"], color)
            bone(draw, base["pelvis"], base[f"{limb}_hip_{side}"], color)
            bone(draw, base[f"{limb}_hip_{side}"], base[f"{limb}_knee_{side}"], color)
            bone(draw, base[f"{limb}_knee_{side}"], base[f"{limb}_foot_{side}"], color)
    for key in base:
        joint(draw, base[key])
    pelvis(draw, base["pelvis"])


def draw_back_legs(image, draw, pose, base):
    head_point = pose.get("head", base["head"])
    neck_point = pose.get("neck", base["neck"])
    bone(draw, head_point, neck_point, BONE)
    bone(draw, neck_point, base["pelvis"], BONE)
    head(draw, head_point)
    for side, color in ((pose["foreground"], FRONT), ("right" if pose["foreground"] == "left" else "left", REAR)):
        bone(draw, pose[f"{side}_hip"], pose[f"{side}_knee"], color, 8)
        bone(draw, pose[f"{side}_knee"], pose[f"{side}_foot"], color, 8)
        for key in (f"{side}_hip", f"{side}_knee", f"{side}_foot"):
            joint(draw, pose[key])
    pelvis(draw, base["pelvis"])


# -------------------------------------------------------------------- main --


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
    enlarged[0].save(path, save_all=True, append_images=enlarged[1:], duration=duration, loop=0)


def contact_sheet(frames, path):
    sheet = Image.new("RGB", (480 * 4, 300 * 2), (17, 24, 39))
    for index, frame in enumerate(frames):
        thumb = frame.resize((480, 300), Image.Resampling.NEAREST)
        sheet.paste(thumb, ((index % 4) * 480, (index // 4) * 300))
    sheet.save(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render skeleton pipeline previews with Pillow (no Godot).")
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
    args = parser.parse_args()

    if args.view == "back" and args.stage in ("pelvis", "arms"):
        raise SystemExit(f"back has no {args.stage} stage yet")

    output = args.output
    output.mkdir(parents=True, exist_ok=True)

    if args.motion:
        # Data-driven pose library: same canvas + draw routines, joint motion
        # defined in workflow/motions/<id>.json (industry pose-library pattern).
        from motion import MotionError, load_motion, render_to_output
        motion = load_motion(args.motion)
        overrides = {}
        if args.stride != 1.0:
            overrides["stride"] = args.stride
        if args.pelvis_bob != 1.0:
            overrides["pelvis_bob"] = args.pelvis_bob
        if args.arm_swing != 1.0:
            overrides["arm_swing"] = args.arm_swing
        try:
            render_to_output(motion, args.view, args.stage, output,
                             params=overrides or None, use_ik=args.ik, fps=args.fps)
        except MotionError as error:
            raise SystemExit(f"motion render failed: {error}")
        return 0

    if args.stage == "skeleton":
        image = render_frame(args.view, args.stage, 0, args.stride, args.pelvis_bob, args.arm_swing)
        out = output / f"{args.view}_base.png"
        image.save(out)
        print(f"SKELETON_RENDER_PASS output={out.resolve()}")
        return 0

    prefix = PREFIX[(args.view, args.stage)]
    frames = [render_frame(args.view, args.stage, i, args.stride, args.pelvis_bob, args.arm_swing) for i in range(FRAME_COUNT)]
    sheet_path = output / f"{prefix}_8frames.png"
    gif_path = output / f"{prefix}.gif"
    contact_sheet(frames, sheet_path)
    make_gif(frames, gif_path)
    print(f"SKELETON_RENDER_PASS frames={len(frames)} sheet={sheet_path.resolve()}")
    print(f"SKELETON_RENDER_GIF={gif_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
