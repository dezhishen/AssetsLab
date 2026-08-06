#!/usr/bin/env python3
"""AssetsLab — 3D 骨架数据 + 投影引擎（阶段 1）。

背景：原架构是"2D 多视图"（每个视图独立存坐标 + 独立动作偏移），
同一关节在 front/side/back 各有一份坐标，冗余且易不一致。
本模块引入 3D 坐标系（x 左右 / y 上下 / z 前后），
从现有 2D 数据【自动合成】3D 坐标，再通过【正交投影】得到任意视角。

数据流：
    2D preset (positions front/side/back)
        ↓ build_skeleton_3d() 自动合成
    3D 骨架 {joint: [x, y, z]} + 3D 骨列表
        ↓ project(joints3d, yaw) 绕 Y 轴旋转 + 正交投影
    2D 屏幕坐标 {joint: (sx, sy)}
        ↓ render_view() 复用 render.py 绘制
    PNG / 帧

阶段 1 范围：3D 骨架数据 + 任意视角（yaw）骨架渲染。
现有 2D 引擎 / 动作 / 验证管线保持零改动。
阶段 2 再对动作做 3D 化（offsets_3d + 3D IK + 动态 z 排序）。
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

from assetslab.models import Preset, SpeciesSkeleton, View

PKG_ROOT = Path(__file__).resolve().parent
PRESETS_ROOT = PKG_ROOT / "presets"
SPECIES_ROOT = PKG_ROOT / "species"

# 视图 → 是否水平镜像（back 从背后看，x 反向）
_VIEW_FLIP = {"front": 1, "back": -1}

# 3D 中线（side 视图 x 基准，用于把"前后"换算成 z 深度）
SIDE_MID = 480.0


def load_preset(preset_id: str) -> Preset:
    with open(PRESETS_ROOT / f"{preset_id}.json") as f:
        return __import__("json").load(f)


def load_species(species_id: str) -> SpeciesSkeleton:
    with open(SPECIES_ROOT / species_id / "skeleton.json") as f:
        return __import__("json").load(f)


def _limb_side_map(chains: dict) -> dict[str, tuple[str, str]]:
    """3D 关节名 → (side_front_name, side_rear_name)。

    自动推导：左肢（*_left）映射到 side 的 front_*（近侧），
    右肢（*_right）映射到 side 的 rear_*（远侧）；躯干关节同名。
    返回 {joint3d: (front_name, rear_name)}。
    """
    out: dict[str, tuple[str, str]] = {}
    for chain in chains.values():
        for j in chain:
            if j.endswith("_left"):
                base = j[:-5]  # 去掉 _left
                out[j] = (f"front_{base}", f"rear_{base}")
            elif j.endswith("_right"):
                base = j[:-6]
                out[j] = (f"front_{base}", f"rear_{base}")
            else:
                out[j] = (j, j)  # 躯干：side 同名（如 neck, chest）
    return out


def build_skeleton_3d(preset_id: str, species_id: str = "human") -> dict:
    """读取 JSON 定义的 3D 骨架（数据驱动）。

    优先读 preset 的 ``positions_3d``（3D 坐标，JSON 显式定义）与
    skeleton 的 ``bones_3d``（3D 骨列表）；缺失时回退到从 2D 数据合成
    （仅用于兼容未 3D 化的预设，程序不产生新数据语义）。

    返回 {"joints": {joint3d: [x, y, z]}, "bones": [[a,b],...], ...}
    """
    preset = load_preset(preset_id)
    species = load_species(species_id)

    # 3D 坐标：JSON 显式定义优先
    joints3d: dict[str, list[float]] = {}
    if preset.get("positions_3d"):
        joints3d = {j: [float(v[0]), float(v[1]), float(v[2])]
                    for j, v in preset["positions_3d"].items()}
    else:
        joints3d = _synthesize_3d(preset, species)  # 兼容回退

    # 3D 骨列表：JSON 显式定义优先
    bones_3d: list[list[str]] = []
    if species.get("bones_3d"):
        bones_3d = [list(b) for b in species["bones_3d"]]
    else:
        for chain in species["chains"].values():
            for a, b in zip(chain, chain[1:]):
                if [a, b] not in bones_3d:
                    bones_3d.append([a, b])

    # 画布中心 / 地面：从 preset 的 canvas 定义读（数据驱动，不硬编码）
    canvas_cfg = preset.get("canvas", {})
    center = [float(canvas_cfg.get("width", 960)) / 2.0,
              float(canvas_cfg.get("height", 600)) / 2.0, 0.0]
    floor_y = float(canvas_cfg.get("floor_y", 470.0))

    # 刚性链：从物种 constraints.rigid_chains 读（数据驱动）
    rigid_chains = (species.get("constraints", {})
                    .get("rigid_chains", {}).get("chains", []))

    return {
        "joints": joints3d,
        "bones": bones_3d,
        "chains": species.get("chains", {}),
        "view2d": _build_view2d(_limb_side_map(species.get("chains", {})),
                                species.get("chains", {}), preset),
        "center": center,
        "floor_y": floor_y,
        "rigid_chains": rigid_chains,
        "species_id": species_id,
    }


def _synthesize_3d(preset: Preset, species: SpeciesSkeleton) -> dict[str, list[float]]:
    """兼容回退：从 2D front(x,y) + side(前后深度) 合成 3D 坐标。"""
    front = preset["positions"]["front"]
    side = preset["positions"]["side"]
    side_map = _limb_side_map(species.get("chains", {}))
    out: dict[str, list[float]] = {}
    for j, (fx, fy) in front.items():
        front_name, _ = side_map.get(j, (j, j))
        sz = side.get(front_name, [SIDE_MID, 0.0])[0]
        out[j] = [fx, fy, sz - SIDE_MID]
    return out


def chains_flat(chains: dict) -> set[str]:
    out: set[str] = set()
    for lst in chains.values():
        out.update(lst)
    return out


def _build_view2d(side_map: dict, chains: dict, preset: Preset) -> dict:
    """构建 3D 关节 → 各 2D 视图关节名 的映射（供投影后对齐绘制）。

    view2d[view][joint3d] = 2d 关节名（front/side/back 各自的名字）。
    """
    pos = preset["positions"]
    view2d: dict[str, dict[str, str]] = {"front": {}, "side": {}, "back": {}}
    flat = chains_flat(chains)
    for j in flat:
        if j in pos["front"]:
            view2d["front"][j] = j
        front_name, rear_name = side_map.get(j, (j, j))
        if front_name in pos["side"]:
            view2d["side"][j] = front_name
        # back：rearr 前后 + left/right
        for suf in ("_left", "_right"):
            bj = f"rear_{j}" if suf in j else j
            if bj in pos["back"]:
                view2d["back"][j] = bj
    return view2d


# --------------------------------------------------------------------------
# 投影（3D 相机：角度 + 距离）
# --------------------------------------------------------------------------

# 默认画布中心（未指定时用标准 960x600；build_skeleton_3d 从 preset canvas 读真实值）
CAM_CX, CAM_CY = 480.0, 300.0
# 骨架中心（相机坐标系原点；= 画布中心时正交投影精确还原 2D 坐标）
_CENTER = (480.0, 300.0, 0.0)


def project(joints3d: dict[str, list[float]], yaw_deg: float = 0.0) -> dict[str, tuple[float, float]]:
    """兼容：绕 Y 轴旋转 yaw 后正交投影（不透视）。返回 {joint: (sx, sy)}。"""
    return project3d(joints3d, yaw_deg=yaw_deg, pitch_deg=0.0, distance=1e9)


def project3d(joints3d: dict[str, list[float]], yaw_deg: float = 0.0,
              pitch_deg: float = 0.0, distance: float = 600.0,
              zoom: float = 1.0, center: tuple[float, float, float] | None = None,
              pan_x: float = 0.0, pan_y: float = 0.0,
              ) -> dict[str, tuple[float, float]]:
    """透视相机投影：yaw（水平角）+ pitch（俯仰角）+ distance（距离）+ pan（平移）。

    - 相机沿视线看向骨架中心（默认画布中心，可传 preset 的 center），先绕 Y 再绕 X。
    - 透视除法：近大远小。distance 越小 → 相机越近 → 透视越强（放大）。
    - zoom 额外缩放（焦距倍率），distance 很大时退化为正交（≈现有 front/side）。
    - pan_x/pan_y：相机观察点平移（像素），等价于移动相机位置/画面平移。
    返回 {joint: (sx, sy)}（画布坐标）。
    """
    yaw = math.radians(yaw_deg)
    pitch = math.radians(pitch_deg)
    cos_y, sin_y = math.cos(yaw), math.sin(yaw)
    cos_p, sin_p = math.cos(pitch), math.sin(pitch)
    cx0, cy0, cz0 = center or _CENTER
    f = max(distance, 1.0) * zoom
    out: dict[str, tuple[float, float]] = {}
    for name, (x, y, z) in joints3d.items():
        # 平移到骨架中心坐标系
        x -= cx0
        y -= cy0
        z -= cz0
        # 绕 Y：x' = x*cos + z*sin ; z' = -x*sin + z*cos
        x1 = x * cos_y + z * sin_y
        z1 = -x * sin_y + z * cos_y
        # 绕 X：y' = y*cos - z*sin ; z' = y*sin + z*cos
        y2 = y * cos_p - z1 * sin_p
        z2 = y * sin_p + z1 * cos_p
        # 透视除法（相机在 +z=distance，看向原点）+ 相机平移（pan）
        z_cam = max(distance - z2, 1.0)
        sx = cx0 + x1 * f / z_cam + pan_x
        sy = cy0 + y2 * f / z_cam + pan_y
        out[name] = (sx, sy)
    return out


# --------------------------------------------------------------------------
# 3D 两骨 IK
# --------------------------------------------------------------------------


def ik3d(hip: list[float], ankle: list[float], l1: float, l2: float,
         pole: tuple[float, float, float] = (0.0, 0.0, 1.0)) -> tuple[list[float], list[float]]:
    """3D 两骨 IK：求 mid（膝/肘）使 |hip-mid|=l1、|mid-ankle|=l2。

    pole 决定弯曲方向（默认 +z 朝前，膝盖朝前弯曲）。
    返回 (mid, clamp 后的 ankle)——超长时踝被拉回保持腿长（脚微离地）。
    """
    hip = [float(v) for v in hip]
    ankle = [float(v) for v in ankle]
    dx, dy, dz = ankle[0]-hip[0], ankle[1]-hip[1], ankle[2]-hip[2]
    dist = math.hypot(dx, dy, dz)
    # clamp 到可解范围（保留一点弯曲，避免伸直临界）
    lo = max(abs(l1-l2), 1e-6)
    hi = (l1 + l2) * 0.99
    if dist > hi:
        # 超长：把末端（踝）沿 hip→踝 方向拉回，保持腿长（脚微离地）
        scale = hi / dist
        dx, dy, dz = dx*scale, dy*scale, dz*scale
        ankle = [hip[0]+dx, hip[1]+dy, hip[2]+dz]
        dist = hi
    elif dist < lo:
        dist = lo
    if dist <= 1e-6:
        return [hip[0], hip[1] - l1, hip[2]], ankle
    u = [dx/dist, dy/dist, dz/dist]
    cos_a = (l1*l1 + dist*dist - l2*l2) / (2.0 * l1 * dist)
    cos_a = max(-1.0, min(1.0, cos_a))
    sin_a = math.sqrt(max(0.0, 1.0 - cos_a*cos_a))
    # pole 投影到垂直 u 的平面
    pdot = pole[0]*u[0] + pole[1]*u[1] + pole[2]*u[2]
    v = [pole[0] - pdot*u[0], pole[1] - pdot*u[1], pole[2] - pdot*u[2]]
    vm = math.hypot(*v)
    if vm < 1e-6:  # pole 平行 u → 退化用任一垂直方向
        v = [0.0, 0.0, 1.0] if abs(u[2]) < 0.9 else [1.0, 0.0, 0.0]
        pdot = v[0]*u[0] + v[1]*u[1] + v[2]*u[2]
        v = [v[0] - pdot*u[0], v[1] - pdot*u[1], v[2] - pdot*u[2]]
        vm = math.hypot(*v) or 1.0
    v = [c / vm for c in v]
    # knee = hip + l1 * (cos_a*u + sin_a*v)
    mid = [hip[i] + l1 * (cos_a*u[i] + sin_a*v[i]) for i in range(3)]
    return mid, ankle


def _limb_ik_chain(root: str, mid: str, tip: str, skel3d: dict, pole=(0.0, 0.0, 1.0)) -> dict:
    """构建单条 3D IK 链（从 3D 骨架当前长度取 l1/l2）。"""
    j = skel3d["joints"]
    l1 = math.dist(j[root], j[mid])
    l2 = math.dist(j[mid], j[tip])
    return {"root": root, "mid": mid, "tip": tip, "l1": l1, "l2": l2, "pole": list(pole)}


def auto_ik3d_chains(skel3d: dict, legs: list[tuple[str, str, str]] | None = None,
                     arms: list[tuple[str, str, str]] | None = None) -> list[dict]:
    """从 3D 骨架自动生成 IK 链（腿膝朝前 pole=+z，臂肘朝后 pole=-z）。"""
    chains = []
    for root, mid, tip in (legs or []):
        chains.append(_limb_ik_chain(root, mid, tip, skel3d, pole=(0.0, 0.0, 1.0)))
    for root, mid, tip in (arms or []):
        chains.append(_limb_ik_chain(root, mid, tip, skel3d, pole=(0.0, 0.0, -1.0)))
    return chains


# --------------------------------------------------------------------------
# 3D 动作引擎（阶段 2 核心）
# --------------------------------------------------------------------------
# 动作在 3D 空间定义：offsets3d[关节] = {x/y/z 轴偏移表达式}，
# 引擎在 3D 求姿势 → 投影到任意视角。与 2D 引擎共用信号 DSL（motion._eval）。


def pose_3d(skel3d: dict, motion3d: dict, index: int, params: dict | None = None) -> dict[str, list[float]]:
    """在 3D 空间求一帧姿势：base_3d + offsets3d + 3D IK。返回 {joint: [x, y, z]}。"""
    from assetslab.motion import _build_signals, _eval, _resolve_params

    ctx = {
        "params": _resolve_params(motion3d, params),
        "index": index,
        "frame_count": int(motion3d.get("frame_count", 8)),
        "phase": math.tau * (index % int(motion3d.get("frame_count", 8))) / int(motion3d.get("frame_count", 8)),
        "signals": _build_signals(motion3d),
    }
    out = {name: [x, y, z] for name, (x, y, z) in skel3d["joints"].items()}
    # root3d：3D 根运动（刚性继承给所有关节）——bob（y 起伏）、lean（z 前倾）等。
    # 由 JSON 定义、参数驱动，实现"整体位移"而不逐关节重复偏移。
    root3d = motion3d.get("root3d", {})
    if root3d:
        rdx = _eval(root3d.get("x", 0.0), ctx)
        rdy = _eval(root3d.get("y", 0.0), ctx)
        rdz = _eval(root3d.get("z", 0.0), ctx)
        for j in out:
            out[j][0] += rdx
            out[j][1] += rdy
            out[j][2] += rdz
    offsets = motion3d.get("offsets3d", {})
    for joint, comp in offsets.items():
        if joint not in out:
            continue
        out[joint][0] += _eval(comp.get("x", 0.0), ctx)
        out[joint][1] += _eval(comp.get("y", 0.0), ctx)
        out[joint][2] += _eval(comp.get("z", 0.0), ctx)
    # 3D IK：保持腿/臂骨长（pole 固定弯曲方向）
    for chain in motion3d.get("ik3d", {}).get("chains", []):
        root, mid, tip = chain["root"], chain["mid"], chain["tip"]
        if root not in out or tip not in out:
            continue
        if chain.get("l1") is None or chain.get("l2") is None:
            l1 = math.dist(skel3d["joints"][root], skel3d["joints"][mid])
            l2 = math.dist(skel3d["joints"][mid], skel3d["joints"][tip])
        else:
            l1, l2 = chain["l1"], chain["l2"]
        out[mid], out[tip] = ik3d(out[root], out[tip], l1, l2,
                                  tuple(chain.get("pole", (0.0, 0.0, 1.0))))
    # 3D 刚性传播：读骨架 rigid_chains（JSON 数据驱动），
    # 跟随关节 = 基准 + 驱动关节位移（绝对定位，幂等），保证脚掌/手掌板不撕裂。
    _propagate_rigid3d(out, skel3d["joints"], skel3d.get("rigid_chains", []))
    return out


def _propagate_rigid3d(out: dict, base: dict, rigid_chains: list[dict]) -> None:
    """3D 刚性传播：跟随关节 = 基准 + 驱动关节位移。

    rigid_chains 来自物种 constraints.rigid_chains（JSON 数据，不含硬编码关节名）。
    """
    for chain in rigid_chains:
        driver = chain["driver"]
        if driver not in out or driver not in base:
            continue
        delta = [out[driver][i] - base[driver][i] for i in range(3)]
        for f in chain.get("follow", []):
            if f in out and f in base:
                out[f] = [base[f][i] + delta[i] for i in range(3)]


def render_motion_3d(skel3d: dict, motion3d: dict, yaw_deg: float = 0.0,
                     pitch_deg: float = 0.0, distance: float = 600.0,
                     zoom: float = 1.0, pan_x: float = 0.0, pan_y: float = 0.0,
                     params: dict | None = None) -> Image.Image:
    """渲染 3D 动作的一帧（首帧），支持角度 + 距离 + 平移。"""
    pose = pose_3d(skel3d, motion3d, 0, params)
    return render_pose(pose, skel3d["bones"], yaw_deg, pitch_deg, distance, zoom,
                       center=tuple(skel3d.get("center", _CENTER)), pan_x=pan_x, pan_y=pan_y)


def render_pose(pose: dict[str, list[float]], bones: list[list[str]],
                yaw_deg: float = 0.0, pitch_deg: float = 0.0,
                distance: float = 600.0, zoom: float = 1.0,
                center: tuple[float, float, float] | None = None,
                pan_x: float = 0.0, pan_y: float = 0.0) -> Image.Image:
    """渲染任意 3D 姿势：角度（yaw/pitch）+ 距离（透视）+ 平移（pan）可调。"""
    from assetslab.render import BONE, JOINT, canvas, head, joint, bone

    image, draw = canvas()
    joints2d = project3d(pose, yaw_deg, pitch_deg, distance, zoom, center=center,
                         pan_x=pan_x, pan_y=pan_y)
    # 头部椭圆（head 关节若有则画，需在骨骼之上）
    if "head" in joints2d:
        head(draw, joints2d["head"], BONE)
    for a, b in bones:
        if a in joints2d and b in joints2d:
            bone(draw, joints2d[a], joints2d[b], BONE)
    for pt in joints2d.values():
        joint(draw, pt)
    return image


def render_view(skel3d: dict, yaw_deg: float = 0.0, pitch_deg: float = 0.0,
                distance: float = 600.0, zoom: float = 1.0,
                pan_x: float = 0.0, pan_y: float = 0.0,
                width: int = 640, height: int = 480) -> Image.Image:
    """渲染 3D 骨架：角度（yaw/pitch）+ 距离（透视）+ 平移（pan）可调。"""
    from assetslab.render import BONE, JOINT, canvas, head, joint, bone

    image, draw = canvas()
    center = tuple(skel3d.get("center", _CENTER))
    joints2d = project3d(skel3d["joints"], yaw_deg, pitch_deg, distance, zoom, center=center,
                         pan_x=pan_x, pan_y=pan_y)
    if "head" in joints2d:
        head(draw, joints2d["head"], BONE)
    for a, b in skel3d["bones"]:
        if a in joints2d and b in joints2d:
            bone(draw, joints2d[a], joints2d[b], BONE)
    for pt in joints2d.values():
        joint(draw, pt)
    return image


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main() -> None:
    import argparse
    import sys

    ap = argparse.ArgumentParser(description="3D 骨架投影预览")
    ap.add_argument("--preset", default="standard")
    ap.add_argument("--species", default="human")
    ap.add_argument("--yaw", type=float, default=0.0, help="视角角（度）：0=front 90=side 180=back 45=斜")
    ap.add_argument("--out", default=None, help="输出 PNG 路径")
    args = ap.parse_args()

    skel3d = build_skeleton_3d(args.preset, args.species)
    img = render_view(skel3d, args.yaw)
    if args.out:
        img.save(args.out)
        print(f"saved {args.out}")
    else:
        img.show()


if __name__ == "__main__":
    main()
